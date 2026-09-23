import SwiftUI

@main
struct DominicanExpressApp: App {
    @State private var store = BankStore()
    var body: some Scene {
        WindowGroup {
            RootView().environment(store).tint(DETheme.blue)
                .environment(\.locale, Locale(identifier: "es_ES"))
        }
    }
}
