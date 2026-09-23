// swift-tools-version: 6.2
import PackageDescription

// Portable tests for models, repositories and view models; the iOS UI lives in the Xcode project.
let package = Package(
    name: "DominicanDomain",
    platforms: [.macOS(.v14), .iOS(.v26)],
    products: [.library(name: "DominicanDomain", targets: ["DominicanDomain"])],
    targets: [
        .target(name: "DominicanDomain", path: "Project", exclude: [
            "App", "DesignSystem", "Resources", "Core/RootView.swift",
            "Features/Home", "Features/SharedAccount", "Features/Profile",
            "Features/Cards/Views", "Features/Cards/Components", "Features/Cards/Models",
            "Features/Activity/Views", "Features/Activity/Components", "Features/Activity/Models",
            "Features/Payments/Views", "Features/Payments/Components",
            "Features/Insights/Views", "Features/Insights/Components", "Features/Insights/Models"
        ], sources: ["Models", "Services", "MockData", "Utilities", "Core/BankStore.swift",
                     "Features/Cards/ViewModels", "Features/Activity/ViewModels", "Features/Payments/ViewModels",
                     "Features/Payments/Models", "Features/Insights/ViewModels"]),
        .testTarget(name: "DominicanDomainTests", dependencies: ["DominicanDomain"], path: "Tests/DominicanDomainTests")
    ]
)
