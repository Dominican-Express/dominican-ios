import Foundation
import Observation

@MainActor @Observable
final class ActivityViewModel {
    var query = ""
    var filter: TransactionKind = .all
    var accountID = "personal"

    func transactions(in data: BankSnapshot, cardID: String? = nil) -> [BankTransaction] {
        data.transactions.filter {
            $0.accountID == accountID && (cardID == nil || $0.cardID == cardID) &&
            (filter == .all || $0.kind == filter) &&
            (query.isEmpty || ($0.title + " " + $0.category).localizedStandardContains(query))
        }
    }

    func csv(_ transactions: [BankTransaction]) -> String {
        let rows = transactions.map { item in
            [item.dateLabel, item.title, NSDecimalNumber(decimal: item.amount).stringValue, item.category]
                .map { "\"" + $0.replacingOccurrences(of: "\"", with: "\"\"") + "\"" }.joined(separator: ";")
        }
        return "EXTRACTO DEMO - SIN VALIDEZ BANCARIA\nFecha;Concepto;Importe EUR;Categoría\n" + rows.joined(separator: "\n")
    }
}
