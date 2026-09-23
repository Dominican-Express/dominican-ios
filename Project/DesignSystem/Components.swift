import SwiftUI

struct BrandMark: View {
    var width: CGFloat = 120
    var body: some View {
        // Vector typography: the supplied board has no standalone brand asset.
        Text("DOMINICAN\nEXPRESS")
            .font(.system(size: width / 7.6, weight: .black, design: .rounded))
            .tracking(-0.8).lineSpacing(-4).multilineTextAlignment(.center)
            .foregroundStyle(Color.white)
            .shadow(color: DETheme.blue, radius: 0, x: 1, y: 1)
            .shadow(color: DETheme.blue, radius: 0, x: -1, y: -1)
            .shadow(color: .white, radius: 0, x: 1, y: -1)
            .frame(width: width)
            .accessibilityLabel("Dominican Express")
    }
}

struct MoneyText: View {
    let amount: Decimal
    var size: CGFloat = 30
    var decimals = 2
    @ScaledMetric(relativeTo: .title2) private var scale: CGFloat = 1
    var body: some View {
        Text(Money.text(amount, decimals: decimals))
            .font(.system(size: size * scale, weight: .semibold)).monospacedDigit()
            .minimumScaleFactor(0.7).lineLimit(1)
    }
}

struct AvatarView: View {
    let initial: String
    var size: CGFloat = 52
    var selected = false
    var body: some View {
        Text(initial).font(.system(size: size * 0.4, weight: .medium))
            .foregroundStyle(DETheme.ink)
            .frame(width: size, height: size)
            .background(LinearGradient(colors: [DETheme.paleBlue, Color.blue.opacity(0.18)], startPoint: .topLeading, endPoint: .bottomTrailing), in: Circle())
            .padding(3)
            .overlay(Circle().stroke(selected ? DETheme.blue : .clear, lineWidth: 2))
    }
}

struct PrimaryButton: View {
    let title: String
    var disabled = false
    var loading = false
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if loading { ProgressView().tint(.white) }
                Text(title).font(.headline)
            }
            .frame(maxWidth: .infinity).padding(.vertical, 16)
            .foregroundStyle(.white)
            .background(DETheme.blue.opacity(disabled ? 0.4 : 1), in: RoundedRectangle(cornerRadius: 12))
        }.buttonStyle(.plain).disabled(disabled || loading)
    }
}

struct SectionHeading: View {
    let title: String
    var actionTitle: String?
    var action: (() -> Void)?
    var body: some View {
        HStack {
            Text(title).font(.headline)
            Spacer()
            if let actionTitle, let action {
                Button(actionTitle, action: action).font(.subheadline).frame(minHeight: 44)
            }
        }
    }
}

struct MenuRow: View {
    let title: String
    let symbol: String
    var detail: String? = nil
    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: symbol).font(.title3).frame(width: 26).foregroundStyle(DETheme.ink)
            Text(title).font(.subheadline)
            Spacer(minLength: 6)
            if let detail { Text(detail).font(.caption).foregroundStyle(DETheme.muted) }
            Image(systemName: "chevron.right").font(.caption).foregroundStyle(DETheme.muted)
        }.frame(minHeight: 54).contentShape(Rectangle())
    }
}

struct TransactionRow: View {
    let transaction: BankTransaction
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: transaction.symbol).font(.system(size: 21, weight: .semibold))
                .frame(width: 43, height: 43).background(DETheme.surface, in: Circle())
            VStack(alignment: .leading, spacing: 4) {
                Text(transaction.title).font(.subheadline)
                Text(transaction.dateLabel).font(.caption).foregroundStyle(DETheme.muted)
            }
            Spacer(minLength: 4)
            Text((transaction.amount > 0 ? "+ " : "− ") + Money.text(abs(transaction.amount)))
                .font(.subheadline.weight(.semibold)).monospacedDigit()
                .foregroundStyle(transaction.amount > 0 ? DETheme.green : DETheme.ink)
                .lineLimit(1).minimumScaleFactor(0.75)
        }.padding(.vertical, 10).accessibilityElement(children: .combine)
    }
}

struct SegmentPicker: View {
    let options: [String]
    @Binding var selection: Int
    var underlined = false
    var body: some View {
        HStack(spacing: underlined ? 0 : 8) {
            ForEach(options.indices, id: \.self) { index in
                Button { selection = index } label: {
                    Text(options[index]).font(.subheadline)
                        .foregroundStyle(selection == index ? (underlined ? DETheme.blue : .white) : DETheme.muted)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(underlined ? .clear : (selection == index ? DETheme.blue : DETheme.surface), in: Capsule())
                        .overlay(alignment: .bottom) {
                            if underlined { Rectangle().fill(selection == index ? DETheme.blue : DETheme.line).frame(height: selection == index ? 2 : 1) }
                        }
                }.buttonStyle(.plain).accessibilityAddTraits(selection == index ? .isSelected : [])
            }
        }
    }
}

struct EmptyState: View {
    let title: String
    let message: String
    let symbol: String
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: symbol).font(.largeTitle).foregroundStyle(DETheme.blue)
            Text(title).font(.headline)
            Text(message).font(.subheadline).foregroundStyle(DETheme.muted).multilineTextAlignment(.center)
        }.frame(maxWidth: .infinity).padding(32)
    }
}

struct DemoFootnote: View {
    var body: some View {
        Label("Entorno demo · Sin operaciones reales", systemImage: "info.circle")
            .font(.caption2).foregroundStyle(DETheme.muted)
            .frame(maxWidth: .infinity).padding(.vertical, 8)
    }
}

struct FieldLabel<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.headline)
            content
        }
    }
}
