import Observation

@MainActor @Observable
final class CardsViewModel {
    var selectedIndex = 0
    var showsVerification = false
    var showsDetails = false
    var showsAddCard = false
}
