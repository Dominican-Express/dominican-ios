import SwiftUI
import UIKit

enum DETheme {
    static let blue = Color(red: 0, green: 0.39, blue: 1)
    static let night = Color(red: 0, green: 0.055, blue: 0.14)
    static let ink = adaptive(light: UIColor(red: 0.025, green: 0.065, blue: 0.28, alpha: 1), dark: UIColor(red: 0.88, green: 0.93, blue: 1, alpha: 1))
    static let muted = adaptive(light: UIColor(red: 0.34, green: 0.43, blue: 0.62, alpha: 1), dark: UIColor(red: 0.61, green: 0.70, blue: 0.84, alpha: 1))
    static let background = adaptive(light: .white, dark: UIColor(red: 0.035, green: 0.055, blue: 0.10, alpha: 1))
    static let surface = adaptive(light: UIColor(red: 0.95, green: 0.96, blue: 0.975, alpha: 1), dark: UIColor(red: 0.08, green: 0.11, blue: 0.18, alpha: 1))
    static let paleBlue = adaptive(light: UIColor(red: 0.89, green: 0.94, blue: 1, alpha: 1), dark: UIColor(red: 0.06, green: 0.17, blue: 0.32, alpha: 1))
    static let green = adaptive(light: UIColor(red: 0, green: 0.48, blue: 0.35, alpha: 1), dark: UIColor(red: 0.25, green: 0.87, blue: 0.64, alpha: 1))
    static let line = Color.primary.opacity(0.07)

    private static func adaptive(light: UIColor, dark: UIColor) -> Color {
        Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? dark : light })
    }
}

struct ScreenStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .foregroundStyle(DETheme.ink)
            .background(DETheme.background)
            .toolbarBackground(DETheme.background, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .navigationBarTitleDisplayMode(.inline)
    }
}

extension View {
    func bankScreen(_ title: String) -> some View {
        navigationTitle(title).modifier(ScreenStyle())
    }
    func bankPanel() -> some View {
        padding(16).background(DETheme.surface, in: RoundedRectangle(cornerRadius: 16))
    }
    func bankInput() -> some View {
        padding(16).background(DETheme.surface, in: RoundedRectangle(cornerRadius: 12))
    }
}
