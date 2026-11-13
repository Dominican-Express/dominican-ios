import Foundation

/// `BankRepository` contra la base de datos real (SurrealDB), sin backend en medio.
///
/// Camino de cada petición: la app inicia sesión con el acceso de registro `banca` y
/// recibe un token que solo lleva los permisos de ese cliente. Las lecturas son
/// consultas SurrealQL por `POST /sql`: la propia base filtra y devuelve solo lo suyo.
/// Los pagos van por los endpoints de `07_api.surql` (`/bizum`, `/transfers`), con un
/// `id` por intento e importe como texto. Contrato completo: `db/APP_INTEGRATION.md`.
///
/// Se activa al lanzar la app con argumentos (por defecto sigue el mock):
///     -surreal-url http://127.0.0.1:8100 -surreal-db cluster
///     -surreal-user ana@dominican.test -surreal-pass demo-ana
actor SurrealBankRepository: BankRepository {
    struct Config: Sendable {
        var baseURL: URL
        var namespace = "dx"
        var database = "live"
        var email: String
        var password: String
    }

    private let config: Config
    private let session: URLSession
    private var token: String?
    /// Nombre del contacto -> teléfono, para el Bizum (la app manda el nombre).
    private var phones: [String: String] = [:]
    private var firstAccount: String?

    init(config: Config, session: URLSession = .shared) {
        self.config = config
        self.session = session
    }

    /// Lee la configuración de los argumentos de lanzamiento; `nil` si no están.
    static func fromLaunchArguments(_ arguments: [String] = ProcessInfo.processInfo.arguments) -> SurrealBankRepository? {
        func value(_ flag: String) -> String? {
            guard let i = arguments.firstIndex(of: flag), i + 1 < arguments.count else { return nil }
            return arguments[i + 1]
        }
        guard let url = value("-surreal-url").flatMap(URL.init(string:)),
              let user = value("-surreal-user"), let pass = value("-surreal-pass") else { return nil }
        var config = Config(baseURL: url, email: user, password: pass)
        if let db = value("-surreal-db") { config.database = db }
        if let ns = value("-surreal-ns") { config.namespace = ns }
        return SurrealBankRepository(config: config)
    }

    // MARK: BankRepository

    func snapshot() async throws -> BankSnapshot {
        let results = try await query("""
            SELECT id, iban, balance, currency, <-owns<-customer.name AS holders FROM account WHERE kind = 'customer';
            SELECT id, account, amount, at, txn.kind AS kind, txn.concept AS concept FROM entry ORDER BY at DESC LIMIT 50;
            SELECT id, account, pan_last4, monthly_limit, math::sum((SELECT VALUE amount FROM card_payment WHERE card = $parent.id AND status = 'approved')) AS spent FROM card;
            SELECT id, name, phone FROM customer WHERE id != $auth.customer;
            SELECT in.name AS name, role, out AS account FROM owns;
            SELECT id, kind, amount, concept, at FROM notification ORDER BY at DESC LIMIT 5;
            """)
        let accounts = rows(results, 0).map { r -> BankAccount in
            let holders = r["holders"] as? [String] ?? []
            return BankAccount(id: text(r["id"]), name: holders.count > 1 ? "Cuenta compartida" : "Cuenta personal",
                               iban: Self.groupIBAN(text(r["iban"])), holder: holders.joined(separator: ", "),
                               balance: decimal(r["balance"]), currency: text(r["currency"], or: "EUR"))
        }
        firstAccount = accounts.first?.id
        let transactions = rows(results, 1).map { r -> BankTransaction in
            let kind = text(r["kind"])
            return BankTransaction(id: text(r["id"]), accountID: text(r["account"]), cardID: nil,
                                   title: (r["concept"] as? String) ?? Self.label(kind), dateLabel: Self.dateLabel(r["at"]),
                                   amount: decimal(r["amount"]), symbol: Self.symbol(kind),
                                   kind: kind == "card" ? .card : .transfer, category: Self.category(kind))
        }
        let cards = rows(results, 2).enumerated().map { i, r -> BankCard in
            let limit = decimal(r["monthly_limit"]), spent = decimal(r["spent"])
            return BankCard(id: text(r["id"]), accountID: text(r["account"]), name: "Dominican Express",
                            lastFour: text(r["pan_last4"]), available: limit - spent, spent: spent,
                            expiry: "", isPrimary: i == 0)
        }
        let people = rows(results, 3)
        phones = Dictionary(people.compactMap { r in (r["phone"] as? String).map { (text(r["name"]), $0) } },
                            uniquingKeysWith: { first, _ in first })
        let contacts = people.map { Contact(id: text($0["id"]), name: text($0["name"])) }
        let members = rows(results, 4).filter { text($0["account"]) == firstAccount }.map {
            AccountMember(id: text($0["name"]), name: text($0["name"]),
                          role: text($0["role"]) == "titular" ? "Titular" : "Cotitular")
        }
        var spending: [String: Decimal] = [:]
        for t in transactions where t.amount < 0 { spending[t.category, default: 0] += -t.amount }
        let categories = spending.sorted { $0.value > $1.value }.map {
            SpendingCategory(id: $0.key, name: $0.key, symbol: "chart.pie.fill", amount: $0.value)
        }
        let notices = rows(results, 5).map { r -> BankNotice in
            let amount = Money.text(decimal(r["amount"]))
            return BankNotice(id: text(r["id"]), title: Self.noticeTitle(text(r["kind"])),
                              detail: [(r["concept"] as? String), amount].compactMap { $0 }.joined(separator: ", "),
                              symbol: Self.symbol(text(r["kind"])))
        }
        return BankSnapshot(accounts: accounts, cards: cards, transactions: transactions, contacts: contacts,
                            members: members, categories: categories, notices: notices)
    }

    /// Paga de verdad: Bizum a un contacto (por su teléfono) o transferencia a un IBAN.
    func simulatePayment(_ request: DemoPaymentRequest) async throws -> DemoReceipt {
        guard request.amount > 0 else { throw DemoError.invalidPayment }
        if request.isRequest { throw SurrealRepositoryError.unsupported("Las solicitudes de dinero no existen en la base todavía.") }
        if phones.isEmpty || firstAccount == nil { _ = try await snapshot() }
        let recipient = request.recipient.replacingOccurrences(of: " ", with: "")
        let id = UUID().uuidString   // uno por intento: repetirlo no cobra dos veces
        var body: [String: String] = ["id": id, "amount": Self.amountText(request.amount)]
        if !request.concept.isEmpty { body["concept"] = String(request.concept.prefix(140)) }
        let path: String
        if recipient.hasPrefix("ES") {
            path = "transfers"
            body["from"] = firstAccount
            body["to_iban"] = recipient
        } else {
            guard let phone = phones[request.recipient] else {
                throw SurrealRepositoryError.unsupported("\(request.recipient) no es un contacto tuyo en el banco.")
            }
            path = "bizum"
            body["to_phone"] = phone
        }
        let (status, reply) = try await api(path, body: body)
        guard status == 200 || status == 201, (reply["status"] as? String) == "done" else {
            throw SurrealRepositoryError.rejected(status, (reply["reason"] as? String) ?? (reply["error"] as? String) ?? "")
        }
        return DemoReceipt(id: text(reply["order"], or: id), recipient: request.recipient,
                           amount: request.amount, isRequest: false)
    }

    // MARK: HTTP

    private func signIn() async throws -> String {
        if let token { return token }
        var req = URLRequest(url: config.baseURL.appending(path: "signin"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.httpBody = try JSONSerialization.data(withJSONObject: [
            "ns": config.namespace, "db": config.database, "ac": "banca",
            "email": config.email, "pass": config.password])
        let (data, response) = try await session.data(for: req)
        guard (response as? HTTPURLResponse)?.statusCode == 200,
              let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw SurrealRepositoryError.signIn
        }
        // 3.x devuelve el token como texto o como {access, refresh}
        let value = (json["token"] as? String) ?? ((json["token"] as? [String: Any])?["access"] as? String)
        guard let value else { throw SurrealRepositoryError.signIn }
        token = value
        return value
    }

    /// Varias sentencias SurrealQL en una petición; devuelve el `result` de cada una.
    private func query(_ sql: String) async throws -> [Any] {
        var req = URLRequest(url: config.baseURL.appending(path: "sql"))
        req.httpMethod = "POST"
        req.httpBody = Data(sql.utf8)
        req.setValue("Bearer \(try await signIn())", forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.setValue(config.namespace, forHTTPHeaderField: "surreal-ns")
        req.setValue(config.database, forHTTPHeaderField: "surreal-db")
        let (data, response) = try await session.data(for: req)
        guard (response as? HTTPURLResponse)?.statusCode == 200,
              let statements = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw SurrealRepositoryError.query(String(decoding: data, as: UTF8.self))
        }
        for s in statements where (s["status"] as? String) != "OK" {
            throw SurrealRepositoryError.query(String(describing: s["result"] ?? ""))
        }
        return statements.map { $0["result"] ?? NSNull() }
    }

    /// POST a un endpoint de 07_api.surql. Reintenta SOLO los conflictos de escritura
    /// (HTTP 400 «can be retried»), con el MISMO id: si el primero llegó a confirmarse,
    /// el reintento recibe esa misma respuesta en vez de pagar otra vez.
    private func api(_ path: String, body: [String: String]) async throws -> (Int, [String: Any]) {
        var req = URLRequest(url: config.baseURL.appending(path: "api/\(config.namespace)/\(config.database)/\(path)"))
        req.httpMethod = "POST"
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        req.setValue("Bearer \(try await signIn())", forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        for attempt in 0...5 {
            let (data, response) = try await session.data(for: req)
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            let raw = String(decoding: data, as: UTF8.self)
            if status == 400, raw.contains("can be retried"), attempt < 5 {
                try await Task.sleep(for: .milliseconds(50 * (attempt + 1)))
                continue
            }
            return (status, (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? ["error": raw])
        }
        throw SurrealRepositoryError.rejected(400, "conflict")
    }

    // MARK: Conversión

    private func rows(_ results: [Any], _ i: Int) -> [[String: Any]] {
        i < results.count ? (results[i] as? [[String: Any]] ?? []) : []
    }
    private func text(_ value: Any?, or fallback: String = "") -> String {
        (value as? String) ?? (value.map { String(describing: $0) } ?? fallback)
    }
    /// El dinero llega como texto («8425.6»): Decimal, nunca Double.
    private func decimal(_ value: Any?) -> Decimal {
        if let s = value as? String { return Decimal(string: s) ?? 0 }
        if let n = value as? NSNumber { return n.decimalValue }
        return 0
    }

    static func amountText(_ amount: Decimal) -> String {
        var value = amount, rounded = Decimal()
        NSDecimalRound(&rounded, &value, 2, .plain)
        return NSDecimalNumber(decimal: rounded).stringValue
    }
    static func groupIBAN(_ iban: String) -> String {
        stride(from: 0, to: iban.count, by: 4).map { i -> String in
            let start = iban.index(iban.startIndex, offsetBy: i)
            return String(iban[start..<(iban.index(start, offsetBy: 4, limitedBy: iban.endIndex) ?? iban.endIndex)])
        }.joined(separator: " ")
    }
    static func dateLabel(_ value: Any?) -> String {
        guard let s = value as? String else { return "" }
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = parser.date(from: s) ?? ISO8601DateFormatter().date(from: s) else { return "" }
        let f = DateFormatter()
        f.locale = Locale(identifier: "es_ES")
        f.dateFormat = "d MMM, HH:mm"
        return f.string(from: date)
    }
    static func label(_ kind: String) -> String {
        ["payroll": "Nómina", "transfer": "Transferencia", "bizum": "Bizum", "card": "Pago con tarjeta", "fee": "Comisión"][kind] ?? kind
    }
    static func symbol(_ kind: String) -> String {
        ["payroll": "briefcase.fill", "transfer": "arrow.left.arrow.right", "bizum": "iphone",
         "card": "creditcard.fill", "fee": "eurosign.circle", "incoming": "arrow.down.left",
         "expense": "arrow.up.right", "card_declined": "exclamationmark.circle.fill"][kind] ?? "circle"
    }
    static func category(_ kind: String) -> String {
        ["payroll": "Ingresos", "card": "Tarjeta", "fee": "Comisiones"][kind] ?? "Transferencias"
    }
    static func noticeTitle(_ kind: String) -> String {
        ["incoming": "Dinero recibido", "payroll": "Has recibido tu nómina", "expense": "Pago realizado",
         "card_declined": "Pago con tarjeta rechazado"][kind] ?? "Aviso"
    }
}

/// El repositorio con el que arranca la app: la base real si los argumentos de
/// lanzamiento lo piden, los datos simulados si no.
func launchRepository(_ arguments: [String] = ProcessInfo.processInfo.arguments) -> any BankRepository {
    SurrealBankRepository.fromLaunchArguments(arguments) ?? MockBankRepository()
}

enum SurrealRepositoryError: LocalizedError {
    case signIn
    case query(String)
    case rejected(Int, String)
    case unsupported(String)

    var errorDescription: String? {
        switch self {
        case .signIn: "No se ha podido iniciar sesión en el banco."
        case .query(let detail): "La base de datos ha rechazado la consulta: \(detail)"
        case .rejected(let status, let reason): "Operación rechazada (\(status)): \(reason)"
        case .unsupported(let detail): detail
        }
    }
}
