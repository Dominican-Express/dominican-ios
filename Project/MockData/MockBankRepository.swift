import Foundation

struct MockBankRepository: BankRepository {
    func snapshot() async throws -> BankSnapshot {
        try await Task.sleep(for: .milliseconds(180))
        return DemoData.snapshot
    }

    func simulatePayment(_ request: DemoPaymentRequest) async throws -> DemoReceipt {
        guard request.amount > 0, !request.recipient.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw DemoError.invalidPayment
        }
        try await Task.sleep(for: .milliseconds(450))
        return DemoReceipt(id: "DEMO-" + UUID().uuidString.prefix(8), recipient: request.recipient, amount: request.amount, isRequest: request.isRequest)
    }
}
