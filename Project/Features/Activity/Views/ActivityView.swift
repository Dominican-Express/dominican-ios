import SwiftUI

struct ActivityView: View {
    @Environment(BankStore.self) private var store
    @State private var model: ActivityViewModel
    let cardID: String?
    init(accountID: String = "personal", cardID: String? = nil) {
        let model = ActivityViewModel()
        model.accountID = accountID
        _model = State(initialValue: model)
        self.cardID = cardID
    }
    var body: some View {
        ScrollView {
            if let data = store.data {
                let transactions = model.transactions(in: data, cardID: cardID)
                VStack(alignment: .leading, spacing: 18) {
                    HStack(spacing: 10) {
                        Image(systemName: "magnifyingglass").foregroundStyle(DETheme.muted)
                        TextField("Buscar movimientos", text: $model.query).font(.subheadline).autocorrectionDisabled()
                        if !model.query.isEmpty { Button { model.query = "" } label: { Image(systemName: "xmark.circle.fill") }.accessibilityLabel("Borrar búsqueda") }
                    }.padding(13).background(DETheme.surface, in: RoundedRectangle(cornerRadius: 12))
                    SegmentPicker(options: TransactionKind.allCases.map(\.rawValue), selection: Binding(get: { TransactionKind.allCases.firstIndex(of: model.filter) ?? 0 }, set: { model.filter = TransactionKind.allCases[$0] }))
                    Text("Marzo 2024").font(.subheadline).foregroundStyle(DETheme.muted)
                    if transactions.isEmpty {
                        EmptyState(title: "Sin movimientos", message: "Prueba otro texto o cambia el filtro.", symbol: "magnifyingglass")
                    }
                    VStack(spacing: 0) {
                        ForEach(transactions) { transaction in
                            NavigationLink { TransactionDetailView(transaction: transaction) } label: { TransactionRow(transaction: transaction) }.buttonStyle(.plain)
                            Divider()
                        }
                    }
                    DemoFootnote()
                }.padding(20)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Menu {
                            if cardID == nil {
                                Picker("Cuenta", selection: $model.accountID) { ForEach(data.accounts) { Text($0.name).tag($0.id) } }
                            }
                            ShareLink(item: DemoStatement(csv: model.csv(transactions)), preview: SharePreview("Extracto demo Dominican Express")) { Label("Exportar extracto demo", systemImage: "square.and.arrow.up") }
                        } label: { Image(systemName: "ellipsis.circle") }.accessibilityLabel("Cuenta y extracto")
                    }
                }
            }
        }.scrollDismissesKeyboard(.interactively).bankScreen("Movimientos")
    }
}

struct TransactionDetailView: View {
    let transaction: BankTransaction
    var body: some View {
        ScrollView {
            VStack(spacing: 25) {
                Image(systemName: transaction.symbol).font(.largeTitle).padding(24).background(DETheme.paleBlue, in: Circle())
                Text(transaction.title).font(.title2.bold())
                Text((transaction.amount < 0 ? "− " : "+ ") + Money.text(abs(transaction.amount))).font(.largeTitle.bold()).foregroundStyle(transaction.amount > 0 ? DETheme.green : DETheme.ink)
                VStack(spacing: 20) {
                    LabeledContent("Fecha", value: transaction.dateLabel)
                    LabeledContent("Categoría", value: transaction.category)
                    LabeledContent("Tipo", value: transaction.kind.rawValue)
                    LabeledContent("Estado", value: "Completado · DEMO")
                    LabeledContent("Referencia", value: "DEMO-" + transaction.id.uppercased())
                }.font(.subheadline).bankPanel()
                DemoFootnote()
            }.padding(24)
        }.bankScreen("Detalle de movimiento")
    }
}
