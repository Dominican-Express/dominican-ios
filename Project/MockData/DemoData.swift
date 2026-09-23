import Foundation

enum DemoData {
    static let snapshot = BankSnapshot(
        accounts: [
            BankAccount(id: "personal", name: "Cuenta personal", iban: "ES00 0000 0000 0000 0000 0001", holder: "Ana García", balance: Decimal(string: "8425.60")!, currency: "EUR"),
            BankAccount(id: "shared", name: "Cuenta compartida", iban: "ES00 0000 0000 0000 0000 0002", holder: "Ana, Carlos y Marta", balance: Decimal(string: "4280.50")!, currency: "EUR")
        ],
        cards: [
            BankCard(id: "primary", accountID: "personal", name: "Dominican Express", lastFour: "4321", available: 3150, spent: 3150, expiry: "09/29", isPrimary: true),
            BankCard(id: "shared-card", accountID: "shared", name: "Dominican Together", lastFour: "8056", available: 2180, spent: 820, expiry: "12/29", isPrimary: false)
        ],
        transactions: [
            BankTransaction(id: "t1", accountID: "personal", cardID: "primary", title: "Supermercado", dateLabel: "Hoy, 14:23", amount: Decimal(string: "-48.90")!, symbol: "cart", kind: .card, category: "Alimentación"),
            BankTransaction(id: "t2", accountID: "personal", cardID: "primary", title: "Uber", dateLabel: "Ayer, 20:10", amount: Decimal(string: "-12.50")!, symbol: "car.fill", kind: .card, category: "Transporte"),
            BankTransaction(id: "t3", accountID: "personal", cardID: "primary", title: "Restaurante", dateLabel: "2 mar, 15:45", amount: -28, symbol: "fork.knife", kind: .card, category: "Alimentación"),
            BankTransaction(id: "t4", accountID: "personal", cardID: nil, title: "Nómina", dateLabel: "1 mar, 09:00", amount: 2300, symbol: "briefcase.fill", kind: .transfer, category: "Ingresos"),
            BankTransaction(id: "t5", accountID: "personal", cardID: "primary", title: "Zara", dateLabel: "28 feb, 18:20", amount: Decimal(string: "-59.95")!, symbol: "bag.fill", kind: .card, category: "Otros"),
            BankTransaction(id: "t6", accountID: "personal", cardID: "primary", title: "Vuelo", dateLabel: "26 feb, 11:15", amount: -320, symbol: "airplane", kind: .card, category: "Ocio"),
            BankTransaction(id: "t7", accountID: "shared", cardID: "shared-card", title: "Compra compartida", dateLabel: "Hoy, 10:15", amount: Decimal(string: "-64.20")!, symbol: "cart", kind: .card, category: "Alimentación")
        ],
        contacts: [Contact(id: "c", name: "Carlos"), Contact(id: "m", name: "Marta"), Contact(id: "l", name: "Lucía"), Contact(id: "j", name: "Javier"), Contact(id: "s", name: "Sofía"), Contact(id: "d", name: "David"), Contact(id: "p", name: "Paula")],
        members: [AccountMember(id: "a", name: "Ana", role: "Administradora"), AccountMember(id: "c", name: "Carlos", role: "Puede gastar"), AccountMember(id: "m", name: "Marta", role: "Puede gastar")],
        categories: [SpendingCategory(id: "food", name: "Alimentación", symbol: "fork.knife", amount: Decimal(string: "412.30")!), SpendingCategory(id: "transport", name: "Transporte", symbol: "car.fill", amount: Decimal(string: "298.20")!), SpendingCategory(id: "leisure", name: "Ocio", symbol: "figure.badminton", amount: Decimal(string: "267.10")!), SpendingCategory(id: "other", name: "Otros", symbol: "scissors", amount: Decimal(string: "268.10")!)],
        notices: [BankNotice(id: "n1", title: "Has recibido tu nómina", detail: "+ € 2.300,00 · 1 mar, 09:00", symbol: "briefcase.fill"), BankNotice(id: "n2", title: "Pago con tarjeta", detail: "Supermercado · − € 48,90", symbol: "cart"), BankNotice(id: "n3", title: "Dinero recibido", detail: "Carlos te ha enviado € 25,00", symbol: "arrow.down.left"), BankNotice(id: "n4", title: "Presupuesto de ocio", detail: "Has superado tu presupuesto de ocio este mes.", symbol: "exclamationmark.circle.fill")]
    )
}
