import Foundation
import Testing
@testable import DominicanDomain

@Test func displayedAmountsMatchReferenceGrouping() {
    #expect(Money.text(Decimal(string: "8425.60")!) == "€ 8.425,60")
    #expect(Money.text(3150, decimals: 0) == "€ 3.150")
    #expect(Money.text(Decimal(string: "48.90")!) == "€ 48,90")
}

@Test func spanishAmountsPreserveCents() {
    #expect(Money.parse("1.245,70") == Decimal(string: "1245.70"))
    #expect(Money.parse("0,01") == Decimal(string: "0.01"))
    #expect(Money.parse("25") == 25)
    for value in ["", "-1", "1,234", "1.2", "1e3", "€ 20", "2,3,4", "NaN"] {
        #expect(Money.parse(value) == nil)
    }
}

@Test @MainActor func filtersCombineAccountCardKindAndSearch() {
    let model = ActivityViewModel()
    model.query = "super"
    #expect(model.transactions(in: DemoData.snapshot).map(\.id) == ["t1"])
    model.filter = .transfer
    #expect(model.transactions(in: DemoData.snapshot).isEmpty)
    model.query = ""
    #expect(model.transactions(in: DemoData.snapshot).map(\.id) == ["t4"])
    model.accountID = "shared"
    model.filter = .all
    #expect(model.transactions(in: DemoData.snapshot, cardID: "shared-card").map(\.id) == ["t7"])
    #expect(model.transactions(in: DemoData.snapshot, cardID: "primary").isEmpty)
}

@Test @MainActor func paymentRequiresRecipientAndValidAmount() {
    let model = PaymentViewModel(mode: .transfer)
    model.amountText = "25"
    #expect(!model.isValid)
    model.selectedContact = Contact(id: "l", name: "Lucía")
    #expect(model.isValid)
    model.amountText = "10.000,01"
    #expect(!model.isValid)
    model.amountText = "0"
    #expect(!model.isValid)
    model.amountText = "25"
    model.usesBankAccount = true
    #expect(!model.isValid)
    model.bankAccountID = "Cuenta demo"
    #expect(model.isValid)
}

@Test @MainActor func demoSubmissionDoesNotMoveMoney() async throws {
    let store = BankStore()
    await store.load()
    let balance = store.data?.accounts.first?.balance
    let model = PaymentViewModel(mode: .bizum)
    await model.submit(using: store)
    #expect(model.receipt?.amount == 25)
    #expect(model.receipt?.recipient == "Lucía")
    #expect(model.receipt?.id.hasPrefix("DEMO-") == true)
    #expect(store.data?.accounts.first?.balance == balance)
    model.reset()
    #expect(model.receipt == nil)
    #expect(!model.isValid)
}

@Test @MainActor func cardBlockingIsIsolatedAndReversible() async {
    let store = BankStore()
    let card = DemoData.snapshot.cards[0]
    store.toggleBlock(card)
    #expect(store.blockedCardIDs.contains(card.id))
    #expect(!store.blockedCardIDs.contains("shared-card"))
    store.toggleBlock(card)
    #expect(store.blockedCardIDs.isEmpty)
}

@Test @MainActor func insightsHaveConsistentTotals() {
    let model = InsightsViewModel()
    let categories = model.categories(from: DemoData.snapshot)
    #expect(model.total(categories) == Decimal(string: "1245.70"))
    let sum = categories.reduce(0.0) { $0 + Money.ratio($1.amount, to: model.total(categories)) }
    #expect(abs(sum - 1) < 0.000001)
    model.previousMonth = true
    #expect(model.total(model.categories(from: DemoData.snapshot)) == Decimal(string: "996.56"))
}

@Test @MainActor func csvContainsOnlyFilteredDemoRows() {
    let model = ActivityViewModel()
    model.filter = .transfer
    let csv = model.csv(model.transactions(in: DemoData.snapshot))
    #expect(csv.contains("SIN VALIDEZ BANCARIA"))
    #expect(csv.contains("Nómina"))
    #expect(!csv.contains("Supermercado"))
}

struct FailingRepository: BankRepository {
    func snapshot() async throws -> BankSnapshot { throw DemoError.invalidPayment }
    func simulatePayment(_ request: DemoPaymentRequest) async throws -> DemoReceipt { throw DemoError.invalidPayment }
}

@Test @MainActor func failuresSurfaceAndClearLoadingState() async {
    let store = BankStore(repository: FailingRepository())
    await store.load()
    #expect(store.errorMessage != nil)
    #expect(store.data == nil)
    #expect(!store.isLoading)
    let model = PaymentViewModel(mode: .bizum)
    await model.submit(using: store)
    #expect(model.errorMessage != nil)
    #expect(!model.isSubmitting)
    #expect(model.receipt == nil)
}
