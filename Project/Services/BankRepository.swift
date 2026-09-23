import Foundation

protocol BankRepository: Sendable {
    func snapshot() async throws -> BankSnapshot
    func simulatePayment(_ request: DemoPaymentRequest) async throws -> DemoReceipt
}

struct DemoPaymentRequest: Sendable {
    let recipient: String
    let amount: Decimal
    let concept: String
    let isRequest: Bool
}

struct DemoReceipt: Identifiable, Sendable {
    let id: String
    let recipient: String
    let amount: Decimal
    let isRequest: Bool
}

enum DemoError: LocalizedError {
    case invalidPayment
    var errorDescription: String? { "Revisa el destinatario y el importe de la operación demo." }
}
