import Foundation
import Observation

@MainActor @Observable
final class PaymentViewModel {
    let mode: PaymentMode
    var selectedContact: Contact?
    var amountText: String
    var concept = ""
    var bankAccountID = ""
    var usesBankAccount = false
    var isRequest = false
    var isSubmitting = false
    var receipt: DemoReceipt?
    var errorMessage: String?

    init(mode: PaymentMode) {
        self.mode = mode
        amountText = mode == .bizum ? "25" : ""
        selectedContact = mode == .bizum ? Contact(id: "l", name: "Lucía") : nil
    }

    var amount: Decimal? { Money.parse(amountText) }
    var recipient: String { usesBankAccount ? bankAccountID : (selectedContact?.name ?? "") }
    var isValid: Bool { (amount ?? 0) > 0 && (amount ?? 0) <= 10000 && !recipient.isEmpty }

    func submit(using store: BankStore) async {
        guard isValid, !isSubmitting else { return }
        isSubmitting = true
        errorMessage = nil
        defer { isSubmitting = false }
        let request = DemoPaymentRequest(recipient: recipient, amount: amount ?? 0, concept: concept, isRequest: isRequest)
        do { receipt = try await store.simulatePayment(request) }
        catch is CancellationError { }
        catch { errorMessage = error.localizedDescription }
    }

    func reset() {
        amountText = ""; concept = ""; receipt = nil; errorMessage = nil
    }
}
