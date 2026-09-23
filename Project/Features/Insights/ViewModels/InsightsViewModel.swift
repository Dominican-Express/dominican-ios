import Foundation
import Observation

@MainActor @Observable
final class InsightsViewModel {
    var previousMonth = false
    func categories(from data: BankSnapshot) -> [SpendingCategory] {
        data.categories.map {
            SpendingCategory(id: $0.id, name: $0.name, symbol: $0.symbol, amount: previousMonth ? $0.amount * Decimal(string: "0.8")! : $0.amount)
        }
    }
    func total(_ categories: [SpendingCategory]) -> Decimal { categories.reduce(0) { $0 + $1.amount } }
}
