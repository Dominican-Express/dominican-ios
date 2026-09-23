import SwiftUI

struct WavePattern: Shape {
    let index: Int
    func path(in rect: CGRect) -> Path {
        let offset = CGFloat(index) * rect.height * 0.10
        var path = Path()
        path.move(to: CGPoint(x: rect.width * 0.30 + offset * 0.26, y: rect.height * 1.15))
        path.addCurve(to: CGPoint(x: rect.width * 1.12, y: rect.height * 0.28 + offset),
                      control1: CGPoint(x: rect.width * 0.57, y: -rect.height * 0.36 + offset),
                      control2: CGPoint(x: rect.width * 0.74, y: rect.height * 0.96 + offset))
        return path
    }
}

struct BankCardView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    let card: BankCard
    var blocked = false
    var aspectRatio: CGFloat = 1.75
    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(red: 0, green: 0.11, blue: 0.48), DETheme.blue, Color(red: 0, green: 0.20, blue: 0.68)], startPoint: .bottomLeading, endPoint: .topTrailing)
            ForEach(0..<7) { index in
                WavePattern(index: index).stroke(Color(red: 0.12, green: 0.55, blue: 1).opacity(0.38 + Double(index) * 0.055), lineWidth: 11)
            }
            VStack(alignment: .leading, spacing: 20) {
                if dynamicTypeSize.isAccessibilitySize {
                    VStack(alignment: .leading, spacing: 10) {
                        BrandMark(width: 92)
                        Text(card.name).font(.subheadline.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
                    }
                } else {
                    HStack(alignment: .top) {
                        Text(card.name).font(.subheadline.weight(.semibold)).frame(maxWidth: 145, alignment: .leading)
                        Spacer()
                        BrandMark(width: 92)
                    }
                }
                Spacer(minLength: 0)
                Image(systemName: blocked ? "lock.fill" : "wave.3.right").font(.title3)
                Text("••••  " + card.lastFour).font(.subheadline.weight(.medium)).tracking(2)
            }.padding(22)
        }
        .foregroundStyle(.white).aspectRatio(dynamicTypeSize.isAccessibilitySize ? 0.78 : aspectRatio, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .saturation(blocked ? 0.3 : 1)
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: blocked)
        .shadow(color: .black.opacity(0.14), radius: 12, y: 7)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(card.name), terminada en \(card.lastFour), \(blocked ? "bloqueada" : "activa")")
    }
}
