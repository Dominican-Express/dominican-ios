import SwiftUI

struct CardsView: View {
    @Environment(BankStore.self) private var store
    @State private var model = CardsViewModel()
    var body: some View {
        ScrollView {
            if let data = store.data, !data.cards.isEmpty {
                let card = data.cards[min(model.selectedIndex, data.cards.count - 1)]
                VStack(spacing: 20) {
                    TabView(selection: $model.selectedIndex) {
                        ForEach(Array(data.cards.enumerated()), id: \.element.id) { index, item in
                            BankCardView(card: item, blocked: store.blockedCardIDs.contains(item.id))
                                .padding(.horizontal, 22).padding(.bottom, 18).tag(index)
                        }
                    }.tabViewStyle(.page(indexDisplayMode: .never)).frame(height: 220)
                    VStack(spacing: 10) {
                        Text(card.isPrimary ? "Principal" : "Compartida").font(.subheadline).foregroundStyle(DETheme.muted)
                        HStack(spacing: 5) {
                            ForEach(data.cards.indices, id: \.self) { index in
                                Circle().fill(index == model.selectedIndex ? DETheme.blue : DETheme.blue.opacity(0.2)).frame(width: 6, height: 6)
                            }
                        }.accessibilityHidden(true)
                        ZStack(alignment: .trailing) {
                            VStack(spacing: 4) {
                                Text("Disponible").font(.headline)
                                if store.hiddenBalance { Text("€ ••••").font(.largeTitle.bold()) }
                                else { MoneyText(amount: card.available, size: 32, decimals: 0) }
                            }.frame(maxWidth: .infinity)
                            Button { store.hiddenBalance.toggle() } label: {
                                Image(systemName: store.hiddenBalance ? "eye.slash" : "eye").frame(width: 44, height: 44).background(DETheme.surface, in: Circle())
                            }.accessibilityLabel(store.hiddenBalance ? "Mostrar disponible" : "Ocultar disponible")
                        }
                    }
                    HStack(spacing: 10) {
                        Button { store.toggleBlock(card) } label: {
                            Label(store.blockedCardIDs.contains(card.id) ? "Desbloquear" : "Bloquear tarjeta", systemImage: store.blockedCardIDs.contains(card.id) ? "lock.open.fill" : "lock.fill")
                                .frame(maxWidth: .infinity, minHeight: 46)
                        }
                        Button { model.showsVerification = true } label: {
                            Label("Ver datos", systemImage: "creditcard").frame(maxWidth: .infinity, minHeight: 46)
                        }
                    }.font(.subheadline).buttonStyle(.bordered).tint(DETheme.blue)
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Límite de gasto mensual").font(.headline)
                        let limit = Decimal(store.cardLimits[card.id] ?? 5000)
                        let ratio = Money.ratio(card.spent, to: limit)
                        HStack {
                            Text(Money.text(card.spent, decimals: 0)).font(.title3.bold()) + Text(" / " + Money.text(limit, decimals: 0)).font(.subheadline)
                            Spacer()
                            Text(ratio, format: .percent.precision(.fractionLength(0))).font(.subheadline).foregroundStyle(DETheme.muted)
                        }
                        ProgressView(value: min(ratio, 1)).tint(DETheme.blue).scaleEffect(y: 2).padding(.vertical, 4)
                    }
                    NavigationLink { CardManagementView(card: card) } label: { MenuRow(title: "Gestión de tarjeta", symbol: "gearshape.fill").padding(.horizontal, 16).background(DETheme.surface, in: RoundedRectangle(cornerRadius: 14)) }.buttonStyle(.plain)
                    DemoFootnote()
                }.padding(.horizontal, 20).padding(.top, 20)
                    .sheet(isPresented: $model.showsDetails) { NavigationStack { CardDetailsView(card: card) } }
            }
        }.bankScreen("Mis tarjetas")
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { model.showsAddCard = true } label: { Image(systemName: "plus").padding(7).background(DETheme.surface, in: Circle()) }.accessibilityLabel("Añadir tarjeta") } }
            .alert("Verificación demo", isPresented: $model.showsVerification) {
                Button("Cancelar", role: .cancel) { }
                Button("Simular verificación") { model.showsDetails = true }
            } message: { Text("Se mostrarán datos ficticios. Esta demo no verifica tu identidad ni utiliza Face ID.") }
            .sheet(isPresented: $model.showsAddCard) { NavigationStack { DemoInformationView(title: "Añadir tarjeta", symbol: "creditcard", message: "Tu demo incluye una tarjeta personal y otra compartida. La emisión de nuevas tarjetas se incorporará cuando exista un servicio bancario.") } }
    }
}

struct CardManagementView: View {
    @Environment(BankStore.self) private var store
    let card: BankCard
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                BankCardView(card: card, blocked: store.blockedCardIDs.contains(card.id))
                Toggle("Tarjeta bloqueada", isOn: Binding(get: { store.blockedCardIDs.contains(card.id) }, set: { _ in store.toggleBlock(card) })).bankPanel()
                NavigationLink { LimitsView(cardID: card.id) } label: { MenuRow(title: "Límites de gasto y retirada", symbol: "slider.horizontal.3") }
                NavigationLink { ActivityView(accountID: card.accountID, cardID: card.id) } label: { MenuRow(title: "Movimientos de tarjeta", symbol: "clock") }
                DemoFootnote()
            }.padding(20)
        }.bankScreen("Gestión de tarjeta")
    }
}

struct CardDetailsView: View {
    @Environment(\.dismiss) private var dismiss
    let card: BankCard
    var body: some View {
        Form {
            Section("Datos sintéticos · verificación simulada") {
                LabeledContent("Titular", value: "Ana García")
                LabeledContent("Número", value: "0000 0000 0000 " + card.lastFour)
                LabeledContent("Caducidad", value: card.expiry)
                LabeledContent("CVV demo", value: "000")
            }
            Text("Estos datos no corresponden a una tarjeta válida.").font(.footnote)
        }.bankScreen("Datos de tarjeta").toolbar { ToolbarItem(placement: .confirmationAction) { Button("Cerrar") { dismiss() } } }
    }
}
