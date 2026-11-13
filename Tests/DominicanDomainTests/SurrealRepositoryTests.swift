import Foundation
import Testing
@testable import DominicanDomain

// Sin base de datos: conversión y configuración.

@Test func surrealAmountsTravelAsTwoDecimalText() {
    #expect(SurrealBankRepository.amountText(Decimal(string: "12.5")!) == "12.5")
    #expect(SurrealBankRepository.amountText(Decimal(string: "12.505")!) == "12.51")
    #expect(SurrealBankRepository.amountText(25) == "25")
}

@Test func surrealIBANIsGroupedInFours() {
    #expect(SurrealBankRepository.groupIBAN("ES1111111111111111111111") == "ES11 1111 1111 1111 1111 1111")
}

@Test func surrealRepositoryNeedsAllLaunchArguments() {
    let full = ["app", "-surreal-url", "http://127.0.0.1:8100", "-surreal-user", "ana@dominican.test",
                "-surreal-pass", "demo-ana", "-surreal-db", "cluster"]
    #expect(SurrealBankRepository.fromLaunchArguments(full) != nil)
    #expect(SurrealBankRepository.fromLaunchArguments(["app"]) == nil)
    #expect(SurrealBankRepository.fromLaunchArguments(Array(full.prefix(5))) == nil)
}

@Test func appStartsOnMockDataUnlessAskedForTheDatabase() {
    #expect(launchRepository(["app"]) is MockBankRepository)
    #expect(launchRepository(["app", "-surreal-url", "http://127.0.0.1:8100", "-surreal-user", "ana@dominican.test",
                              "-surreal-pass", "demo-ana"]) is SurrealBankRepository)
}

// Contra una base real (esquema + 01_seed): solo con SURREAL_IT_URL, por ejemplo
//   ./db/demo/demo.sh cluster-up
//   SURREAL_IT_URL=http://127.0.0.1:8100 SURREAL_IT_DB=cluster ./scripts/test.sh --filter Surreal

private let itURL = ProcessInfo.processInfo.environment["SURREAL_IT_URL"].flatMap(URL.init(string:))
private let itDB = ProcessInfo.processInfo.environment["SURREAL_IT_DB"] ?? "live"

private func ana(password: String = "demo-ana") -> SurrealBankRepository {
    SurrealBankRepository(config: .init(baseURL: itURL!, database: itDB, email: "ana@dominican.test",
                                        password: password))
}

@Test(.enabled(if: itURL != nil)) func surrealAnaSeesOnlyHerOwnData() async throws {
    let snapshot = try await ana().snapshot()
    #expect(snapshot.accounts.map(\.id) == ["account:ana"])
    #expect(snapshot.accounts.first?.holder == "Ana García, Luis Romero")
    #expect(snapshot.contacts.map(\.name) == ["Luis Romero"])   // su cotitular, nadie más
    #expect(snapshot.cards.map(\.lastFour) == ["4242"])
    #expect(Set(snapshot.members.map(\.role)) == ["Titular", "Cotitular"])
}

@Test(.enabled(if: itURL != nil)) func surrealBizumIsChargedExactlyOnce() async throws {
    let repo = ana()
    let before = try await repo.snapshot().accounts[0].balance
    let receipt = try await repo.simulatePayment(.init(recipient: "Luis Romero", amount: Decimal(string: "12.50")!,
                                                       concept: "Cena", isRequest: false))
    #expect(receipt.id.count == 36)
    let after = try await repo.snapshot().accounts[0].balance
    #expect(before - after == Decimal(string: "12.50")!)
}

@Test(.enabled(if: itURL != nil)) func surrealWrongPasswordIsRefused() async {
    await #expect(throws: SurrealRepositoryError.self) { _ = try await ana(password: "wrong").snapshot() }
}

@Test(.enabled(if: itURL != nil)) func surrealStrangerIsNotAContact() async {
    await #expect(throws: SurrealRepositoryError.self) {
        _ = try await ana().simulatePayment(.init(recipient: "Marta Sanz", amount: 5, concept: "", isRequest: false))
    }
}
