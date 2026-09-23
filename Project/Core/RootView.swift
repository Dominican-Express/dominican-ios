import SwiftUI

enum AppTab: String, CaseIterable, Identifiable {
    case home = "Inicio", cards = "Tarjetas", activity = "Actividad", payments = "Pagos", profile = "Perfil"
    var id: Self { self }
    var symbol: String {
        switch self {
        case .home: "house"
        case .cards: "creditcard"
        case .activity: "clock.arrow.circlepath"
        case .payments: "slider.horizontal.3"
        case .profile: "person"
        }
    }
}

struct RootView: View {
    @Environment(BankStore.self) private var store
    @State private var selection: AppTab = .home
    var body: some View {
        Group {
            if store.data != nil {
                TabView(selection: $selection) {
                    NavigationStack { HomeView(selection: $selection) }.tag(AppTab.home)
                    NavigationStack { CardsView() }.tag(AppTab.cards)
                    NavigationStack { ActivityView() }.tag(AppTab.activity)
                    NavigationStack { PaymentView(mode: .transfer) }.tag(AppTab.payments)
                    NavigationStack { ProfileView() }.tag(AppTab.profile)
                }
                .toolbar(.hidden, for: .tabBar)
                .safeAreaInset(edge: .bottom, spacing: 0) { AppTabBar(selection: $selection) }
            } else if let error = store.errorMessage {
                VStack {
                    EmptyState(title: "No se pudo cargar la demo", message: error, symbol: "wifi.exclamationmark")
                    Button("Reintentar") { Task { await store.load() } }
                }
            } else {
                VStack(spacing: 24) { BrandMark(width: 190); ProgressView().tint(.white) }
                    .frame(maxWidth: .infinity, maxHeight: .infinity).background(DETheme.night)
            }
        }.task { await store.load() }
    }
}

struct AppTabBar: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Binding var selection: AppTab
    var body: some View {
        HStack(spacing: 0) {
            ForEach(AppTab.allCases) { tab in
                Button { selection = tab } label: {
                    VStack(spacing: 5) {
                        Image(systemName: tab.symbol).font(.system(size: 19, weight: selection == tab ? .semibold : .regular))
                            .symbolVariant(selection == tab && (tab == .home || tab == .profile || tab == .cards) ? .fill : .none)
                        Text(tab.rawValue).font(.caption2)
                    }
                    .foregroundStyle(selection == tab ? DETheme.blue : DETheme.muted)
                    .frame(maxWidth: .infinity, minHeight: 54)
                    .contentShape(Rectangle())
                }.buttonStyle(.plain).accessibilityAddTraits(selection == tab ? .isSelected : [])
                    .accessibilityIdentifier("tab-\(tab)")
                    .accessibilityShowsLargeContentViewer { Label(tab.rawValue, systemImage: tab.symbol) }
            }
        }.animation(reduceMotion ? nil : .easeInOut(duration: 0.18), value: selection)
            .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
            .padding(.horizontal, 8).padding(.top, 5)
            .background(DETheme.background).overlay(alignment: .top) { DETheme.line.frame(height: 1) }
    }
}
