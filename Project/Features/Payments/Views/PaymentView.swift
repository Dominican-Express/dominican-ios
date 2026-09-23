import SwiftUI

struct PaymentView: View {
    @Environment(BankStore.self) private var store
    @State private var model: PaymentViewModel
    @State private var showsContacts = false
    @State private var showsReview = false
    @FocusState private var inputFocused: Bool
    init(mode: PaymentMode) { _model = State(initialValue: PaymentViewModel(mode: mode)) }
    var body: some View {
        ScrollView {
            if let data = store.data {
                VStack(alignment: .leading, spacing: 24) {
                    SegmentPicker(options: model.mode == .bizum ? ["Enviar", "Solicitar"] : ["Contactos", "Cuenta bancaria"], selection: Binding(get: { (model.mode == .bizum ? model.isRequest : model.usesBankAccount) ? 1 : 0 }, set: { value in if model.mode == .bizum { model.isRequest = value == 1 } else { model.usesBankAccount = value == 1 } }), underlined: true)
                    if model.usesBankAccount {
                        FieldLabel(title: "Cuenta de destino") {
                            Picker("Cuenta demo del banco", selection: $model.bankAccountID) {
                                Text("Selecciona una cuenta").tag("")
                                Text("Cuenta compartida · 0002").tag("Cuenta compartida · 0002")
                                Text("Carlos · Cuenta demo 0003").tag("Carlos · Cuenta demo 0003")
                            }.tint(DETheme.ink).bankInput()
                        }
                        Text("Solo cuentas ficticias de Dominican Express.").font(.caption).foregroundStyle(DETheme.muted)
                    } else {
                        VStack(spacing: 12) {
                            SectionHeading(title: model.mode == .bizum ? "Contactos" : "Contactos favoritos", actionTitle: "Ver todos") { showsContacts = true }
                            ContactPicker(contacts: displayContacts(data), selected: $model.selectedContact, showsNew: model.mode == .bizum, onNew: { showsContacts = true })
                        }
                    }
                    FieldLabel(title: "Importe") {
                        HStack {
                            Text("€").foregroundStyle(DETheme.muted)
                            TextField("0,00", text: $model.amountText).keyboardType(.decimalPad).focused($inputFocused)
                                .accessibilityLabel("Importe en euros")
                        }.font(.title2.weight(.medium)).bankInput()
                        if !model.amountText.isEmpty && (model.amount == nil || (model.amount ?? 0) <= 0 || (model.amount ?? 0) > 10000) {
                            Text("Introduce entre 0,01 y 10.000,00 €, con coma decimal.").font(.caption).foregroundStyle(.orange)
                        }
                    }
                    if model.mode == .transfer {
                        FieldLabel(title: "Concepto") {
                            TextField("Ej. Cena, regalo, alquiler…", text: $model.concept).font(.subheadline).bankInput().focused($inputFocused)
                        }
                    } else {
                        FieldLabel(title: "Para") {
                            Button { showsContacts = true } label: {
                                HStack {
                                    AvatarView(initial: model.selectedContact?.initial ?? "?", size: 28)
                                    Text(model.selectedContact?.name ?? "Selecciona un contacto").font(.subheadline)
                                    Spacer()
                                }.padding(8).background(DETheme.surface, in: RoundedRectangle(cornerRadius: 12))
                            }.buttonStyle(.plain)
                        }
                    }
                    PrimaryButton(title: "Continuar", disabled: !model.isValid) { inputFocused = false; showsReview = true }
                        .accessibilityIdentifier("payment-continue")
                    DemoFootnote()
                }.padding(.horizontal, 20).padding(.top, 8)
                .sheet(isPresented: $showsContacts) { NavigationStack { ContactListView(contacts: data.contacts) { model.selectedContact = $0 } } }
            }
        }.scrollDismissesKeyboard(.interactively).bankScreen(model.mode.rawValue)
            .toolbar { ToolbarItemGroup(placement: .keyboard) { Spacer(); Button("Listo") { inputFocused = false } } }
            .navigationDestination(isPresented: $showsReview) { PaymentReviewView(model: model) }
    }

    private func displayContacts(_ data: BankSnapshot) -> [Contact] {
        if model.mode == .transfer { return Array(data.contacts.prefix(4)) }
        return data.contacts.filter { $0.id == "l" } + data.contacts.filter { $0.id != "l" }
    }
}

struct PaymentReviewView: View {
    @Environment(BankStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    @Bindable var model: PaymentViewModel
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                if let receipt = model.receipt {
                    Image(systemName: "checkmark.circle.fill").font(.system(size: 64)).foregroundStyle(DETheme.green)
                    Text(receipt.isRequest ? "Solicitud simulada" : "Envío simulado").font(.title2.bold())
                    MoneyText(amount: receipt.amount, size: 36)
                    Text("Para \(receipt.recipient)").font(.headline)
                    Text("No se ha movido dinero ni se ha contactado con nadie. Los saldos de la demo se mantienen.").multilineTextAlignment(.center).foregroundStyle(DETheme.muted)
                    Text(receipt.id).font(.caption.monospaced()).textSelection(.enabled)
                    PrimaryButton(title: "Volver") { model.reset(); dismiss() }
                } else {
                    AvatarView(initial: model.selectedContact?.initial ?? "C", size: 80)
                    Text(model.isRequest ? "Revisar solicitud" : "Revisar envío").font(.title2.bold())
                    MoneyText(amount: model.amount ?? 0, size: 36)
                    VStack(spacing: 18) {
                        LabeledContent("Para", value: model.recipient)
                        LabeledContent("Desde", value: "Cuenta personal · 0001")
                        LabeledContent("Concepto", value: model.concept.isEmpty ? "Sin concepto" : model.concept)
                        LabeledContent("Comisión demo", value: "€ 0,00")
                    }.font(.subheadline).bankPanel()
                    if let error = model.errorMessage { Text(error).foregroundStyle(.red).font(.caption) }
                    PrimaryButton(title: model.isRequest ? "Simular solicitud" : "Simular envío", loading: model.isSubmitting) { Task { await model.submit(using: store) } }
                    DemoFootnote()
                }
            }.padding(24)
        }.bankScreen("Confirmación").navigationBarBackButtonHidden(model.isSubmitting || model.receipt != nil)
    }
}

struct DemoCardPaymentView: View {
    @Environment(BankStore.self) private var store
    @State private var showsResult = false
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                if let card = store.data?.cards.first {
                    BankCardView(card: card, blocked: store.blockedCardIDs.contains(card.id))
                    Image(systemName: "wave.3.right.circle").font(.system(size: 72)).foregroundStyle(DETheme.blue)
                    Text("Pago con tarjeta").font(.title2.bold())
                    Text("Simula un pago de € 12,50 con tu tarjeta principal.").multilineTextAlignment(.center).foregroundStyle(DETheme.muted)
                    PrimaryButton(title: "Simular pago", disabled: store.blockedCardIDs.contains(card.id)) { showsResult = true }
                    if store.blockedCardIDs.contains(card.id) { Text("Desbloquea la tarjeta para continuar.").font(.caption) }
                    DemoFootnote()
                }
            }.padding(24)
        }.bankScreen("Pagar").alert("Pago demo completado", isPresented: $showsResult) { Button("Aceptar", role: .cancel) { } } message: { Text("No se ha realizado ningún cargo de € 12,50.") }
    }
}

struct AddMoneyView: View {
    @State private var amount = ""
    @State private var completed = false
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text("Añadir dinero a tu cuenta").font(.title2.bold())
                Text("Ingreso de demostración desde una cuenta externa ficticia.").foregroundStyle(DETheme.muted)
                FieldLabel(title: "Importe") { TextField("0,00", text: $amount).keyboardType(.decimalPad).bankInput() }
                PrimaryButton(title: "Simular ingreso", disabled: (Money.parse(amount) ?? 0) <= 0 || (Money.parse(amount) ?? 0) > 10000) { completed = true }
                DemoFootnote()
            }.padding(20)
        }.bankScreen("Añadir dinero").alert("Ingreso simulado", isPresented: $completed) { Button("Aceptar") { amount = "" } } message: { Text("No se ha realizado ningún ingreso ni modificado el saldo.") }
    }
}
