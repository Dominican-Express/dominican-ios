import SwiftUI

struct InsightsView: View {
    @Environment(BankStore.self) private var store
    @State private var model = InsightsViewModel()
    private let colors: [Color] = [DETheme.blue, .cyan, .orange, .gray]
    var body: some View {
        ScrollView {
            if let data = store.data {
                let categories = model.categories(from: data)
                VStack(spacing: 22) {
                    InsightRing(categories: categories).frame(maxWidth: 290).padding(.horizontal, 22)
                    VStack(spacing: 18) {
                        ForEach(Array(categories.enumerated()), id: \.element.id) { index, category in
                            NavigationLink { CategoryDetailView(category: category, previousMonth: model.previousMonth) } label: {
                                HStack(spacing: 12) {
                                    Image(systemName: category.symbol).font(.subheadline).frame(width: 32, height: 32).background(colors[index].opacity(0.3), in: Circle())
                                    Text(category.name).font(.subheadline)
                                    Spacer()
                                    Text(Money.text(category.amount)).font(.subheadline.weight(.semibold)).monospacedDigit()
                                    Text(Money.ratio(category.amount, to: model.total(categories)), format: .percent.precision(.fractionLength(0)))
                                        .font(.caption).foregroundStyle(DETheme.muted).frame(width: 36, alignment: .trailing)
                                }
                            }.buttonStyle(.plain)
                        }
                    }
                    if !model.previousMonth, let leisure = categories.first(where: { $0.id == "leisure" }) {
                        NavigationLink { CategoryDetailView(category: leisure, previousMonth: false) } label: {
                            HStack(spacing: 12) {
                                Image(systemName: "exclamationmark.circle.fill").font(.title2).foregroundStyle(.orange)
                                Text("Has superado tu presupuesto de ocio este mes.").font(.caption).multilineTextAlignment(.leading)
                                Spacer(minLength: 0)
                                Image(systemName: "chevron.right").foregroundStyle(.orange)
                            }.padding(18).background(Color.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 14))
                        }.buttonStyle(.plain)
                    }
                    DemoFootnote()
                }.padding(20)
            }
        }.bankScreen("Insights")
            .toolbar { ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button("Este mes") { model.previousMonth = false }
                    Button("Mes anterior") { model.previousMonth = true }
                } label: { HStack(spacing: 4) { Text(model.previousMonth ? "Mes anterior" : "Este mes"); Image(systemName: "chevron.down") }.font(.caption) }
            } }
    }
}

struct CategoryDetailView: View {
    let category: SpendingCategory
    let previousMonth: Bool
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Image(systemName: category.symbol).font(.largeTitle).padding(25).background(DETheme.paleBlue, in: Circle())
                Text(previousMonth ? "Mes anterior" : "Este mes").foregroundStyle(DETheme.muted)
                MoneyText(amount: category.amount, size: 36)
                Text("Total demo de \(category.name.lowercased())").font(.headline)
                if category.id == "leisure" {
                    LabeledContent("Presupuesto mensual", value: "€ 250,00").bankPanel()
                    Text(category.amount > 250 ? "Has superado el presupuesto en " + Money.text(category.amount - 250) : "Tu gasto está dentro del presupuesto.")
                        .font(.subheadline).foregroundStyle(DETheme.muted)
                }
                Text("El resumen mensual es un conjunto demo independiente de los movimientos recientes.").font(.caption).foregroundStyle(DETheme.muted).multilineTextAlignment(.center)
                DemoFootnote()
            }.padding(24)
        }.bankScreen(category.name)
    }
}
