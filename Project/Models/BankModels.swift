import Foundation

struct BankAccount: Identifiable, Sendable {
    let id: String
    let name: String
    let iban: String
    let holder: String
    let balance: Decimal
    let currency: String
}

struct BankCard: Identifiable, Sendable {
    let id: String
    let accountID: String
    let name: String
    let lastFour: String
    let available: Decimal
    let spent: Decimal
    let expiry: String
    let isPrimary: Bool
}

enum TransactionKind: String, CaseIterable, Sendable {
    case all = "Todos", card = "Tarjeta", transfer = "Transferencias"
}

struct BankTransaction: Identifiable, Hashable, Sendable {
    let id: String
    let accountID: String
    let cardID: String?
    let title: String
    let dateLabel: String
    let amount: Decimal
    let symbol: String
    let kind: TransactionKind
    let category: String
}

struct Contact: Identifiable, Hashable, Sendable {
    let id: String
    let name: String
    var initial: String { String(name.prefix(1)) }
}

struct AccountMember: Identifiable, Sendable {
    let id: String
    let name: String
    var role: String
    var initial: String { String(name.prefix(1)) }
}

struct SpendingCategory: Identifiable, Sendable {
    let id: String
    let name: String
    let symbol: String
    let amount: Decimal
}

struct BankNotice: Identifiable, Sendable {
    let id: String
    let title: String
    let detail: String
    let symbol: String
}

struct BankSnapshot: Sendable {
    let accounts: [BankAccount]
    let cards: [BankCard]
    let transactions: [BankTransaction]
    let contacts: [Contact]
    let members: [AccountMember]
    let categories: [SpendingCategory]
    let notices: [BankNotice]
}
