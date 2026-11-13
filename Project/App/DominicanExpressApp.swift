import SwiftUI

@main
struct DominicanExpressApp: App {
    // Datos simulados por defecto; la base real si se lanza con -surreal-url, -surreal-user
    // y -surreal-pass (en el esquema compartido, desactivados: Edit Scheme > Run > Arguments).
    @State private var store = BankStore(repository: launchRepository())
    var body: some Scene {
        WindowGroup {
            RootView().environment(store).tint(DETheme.blue)
                .environment(\.locale, Locale(identifier: "es_ES"))
        }
    }
}
