import SwiftUI

struct HomeView: View {
    @Environment(BankStore.self) private var store
    @Binding var selection: AppTab
    var body: some View {
        ScrollView {
            if let data = store.data, let account = data.accounts.first, let card = data.cards.first {
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        BrandMark(width: 120)
                        Spacer()
                        NavigationLink { NotificationsView() } label: {
                            Image(systemName: "bell").font(.title3).frame(width: 44, height: 44)
                        }.accessibilityLabel("Notificaciones")
                    }
                    Text("Buenos días, Ana").font(.title3)
                    NavigationLink { CardsView() } label: { BankCardView(card: card, blocked: store.blockedCardIDs.contains(card.id), aspectRatio: 1.9) }.buttonStyle(.plain)
                    HStack(alignment: .center) {
                        NavigationLink { AccountDetailView(account: account) } label: {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("Saldo total").font(.subheadline).foregroundStyle(.white.opacity(0.8))
                                if store.hiddenBalance { Text("€ ••••••").font(.title.bold()) }
                                else { MoneyText(amount: account.balance, size: 31) }
                            }
                        }.buttonStyle(.plain)
                        Spacer()
                        Button { store.hiddenBalance.toggle() } label: {
                            Image(systemName: store.hiddenBalance ? "eye.slash" : "eye").frame(width: 44, height: 44)
                                .background(.white.opacity(0.06), in: Circle())
                        }.accessibilityLabel(store.hiddenBalance ? "Mostrar saldo" : "Ocultar saldo")
                    }
                    HStack(alignment: .top, spacing: 10) {
                        NavigationLink { PaymentView(mode: .transfer) } label: { QuickAction(title: "Enviar", symbol: "paperplane") }
                        NavigationLink { PaymentView(mode: .bizum) } label: { QuickAction(title: "Bizum", symbol: "bolt.horizontal") }
                        NavigationLink { DemoCardPaymentView() } label: { QuickAction(title: "Pagar", symbol: "qrcode.viewfinder") }
                        NavigationLink { AddMoneyView() } label: { QuickAction(title: "Añadir\ndinero", symbol: "plus.app.fill") }
                    }.buttonStyle(.plain)
                }.padding(20).foregroundStyle(.white)
                VStack(alignment: .leading, spacing: 0) {
                    SectionHeading(title: "Actividad reciente", actionTitle: "Ver todo") { selection = .activity }
                    ForEach(data.transactions.filter { ["t1", "t2", "t4"].contains($0.id) }) { transaction in
                        NavigationLink { TransactionDetailView(transaction: transaction) } label: { TransactionRow(transaction: transaction) }.buttonStyle(.plain)
                        Divider()
                    }
                    VStack(spacing: 0) {
                        NavigationLink { SharedAccountView() } label: { MenuRow(title: "Cuenta compartida", symbol: "person.2") }
                        Divider()
                        NavigationLink { InsightsView() } label: { MenuRow(title: "Insights", symbol: "chart.pie") }
                    }.padding(.top, 12)
                    DemoFootnote()
                }.padding(.horizontal, 20).padding(.top, 5)
                    .foregroundStyle(DETheme.ink)
                    .background(DETheme.background, in: UnevenRoundedRectangle(topLeadingRadius: 18, topTrailingRadius: 18))
            }
        }
        .background(DETheme.night).toolbar(.hidden, for: .navigationBar)
    }
}

private struct QuickAction: View {
    let title: String
    let symbol: String
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: symbol).font(.system(size: 23, weight: .medium)).foregroundStyle(DETheme.blue)
                .frame(width: 56, height: 56)
                .background(LinearGradient(colors: [.white, Color(red: 0.63, green: 0.81, blue: 1)], startPoint: .topLeading, endPoint: .bottomTrailing), in: Circle())
                .overlay(Circle().stroke(.white.opacity(0.7), lineWidth: 1))
            Text(title).font(.caption.weight(.medium)).multilineTextAlignment(.center)
        }.frame(maxWidth: .infinity)
    }
}
