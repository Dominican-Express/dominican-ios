import Foundation
import Observation

@MainActor @Observable
final class BankStore {
    private let repository: any BankRepository
    private(set) var data: BankSnapshot?
    private(set) var isLoading = false
    var errorMessage: String?
    var hiddenBalance = false
    var blockedCardIDs: Set<String> = []
    var cardLimits: [String: Double] = ["primary": 5000, "shared-card": 3000]
    var withdrawalLimit = 600.0
    var notificationsEnabled = true
    var lowBalanceAlerts = true
    var suspiciousActivityAlerts = true
    var extraMembers: [AccountMember] = []
    var memberRoles: [String: String] = [:]

    init(repository: any BankRepository = MockBankRepository()) { self.repository = repository }

    func load() async {
        guard data == nil, !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        do { data = try await repository.snapshot(); errorMessage = nil }
        catch is CancellationError { }
        catch { errorMessage = error.localizedDescription }
    }

    func toggleBlock(_ card: BankCard) {
        if blockedCardIDs.contains(card.id) { blockedCardIDs.remove(card.id) }
        else { blockedCardIDs.insert(card.id) }
    }

    func simulatePayment(_ request: DemoPaymentRequest) async throws -> DemoReceipt {
        try await repository.simulatePayment(request)
    }
}
