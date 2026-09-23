import SwiftUI

struct InsightRing: View {
    let categories: [SpendingCategory]
    private let colors: [Color] = [DETheme.blue, Color(red: 0.43, green: 0.76, blue: 1), Color(red: 1, green: 0.72, blue: 0.19), Color(red: 0.82, green: 0.86, blue: 0.91)]
    private var total: Decimal { categories.reduce(0) { $0 + $1.amount } }
    var body: some View {
        ZStack {
            ForEach(Array(categories.enumerated()), id: \.element.id) { index, category in
                let start = categories.prefix(index).reduce(Decimal.zero) { $0 + $1.amount }
                Circle().trim(from: Money.ratio(start, to: total), to: Money.ratio(start + category.amount, to: total))
                    .stroke(colors[index % colors.count], style: StrokeStyle(lineWidth: 34, lineCap: .butt)).rotationEffect(.degrees(-90))
            }
            VStack(spacing: 5) {
                MoneyText(amount: total, size: 23)
                Text("Gasto total").font(.caption).foregroundStyle(DETheme.muted)
            }.padding(32)
        }.padding(19).aspectRatio(1, contentMode: .fit)
            .accessibilityElement(children: .ignore).accessibilityLabel("Gasto total: " + Money.text(total))
    }
}
