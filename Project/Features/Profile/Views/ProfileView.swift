import SwiftUI

struct ProfileView: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                NavigationLink { PersonalDetailsView() } label: {
                    HStack(spacing: 14) { AvatarView(initial: "A", size: 72); Text("Ana García").font(.title3.bold()); Spacer(); Image(systemName: "chevron.right").font(.subheadline) }
                        .padding(.vertical, 22)
                }.buttonStyle(.plain)
                VStack(spacing: 0) {
                    NavigationLink { NotificationsView() } label: { MenuRow(title: "Notificaciones", symbol: "bell") }
                    Divider()
                    NavigationLink { LimitsView() } label: { MenuRow(title: "Límites", symbol: "viewfinder") }
                    Divider()
                    NavigationLink { RecurringPaymentsView() } label: { MenuRow(title: "Domiciliaciones", symbol: "calendar") }
                    Divider()
                    NavigationLink { DocumentsView() } label: { MenuRow(title: "Documentos", symbol: "doc") }
                    Divider()
                    NavigationLink { SecurityView() } label: { MenuRow(title: "Seguridad", symbol: "checkmark.shield") }
                }.padding(.horizontal, 16).padding(.vertical, 4)
                    .background(DETheme.background, in: RoundedRectangle(cornerRadius: 15))
                    .shadow(color: .black.opacity(0.045), radius: 14, y: 4)
                DemoFootnote().padding(.top, 20)
            }.padding(20)
        }.bankScreen("Perfil")
    }
}

struct PersonalDetailsView: View {
    var body: some View {
        Form {
            Section { HStack { AvatarView(initial: "A", size: 68); VStack(alignment: .leading) { Text("Ana García").font(.headline); Text("Perfil de demostración").font(.caption) } } }
            Section("Datos personales ficticios") {
                LabeledContent("Nombre", value: "Ana García")
                LabeledContent("Correo", value: "ana@example.com")
                LabeledContent("Residencia", value: "Madrid, España")
            }
            Section { Text("Los datos de este perfil son sintéticos y no se guardan fuera de la aplicación.").font(.footnote) }
        }.bankScreen("Datos personales")
    }
}

struct NotificationsView: View {
    @Environment(BankStore.self) private var store
    var body: some View {
        @Bindable var store = store
        ScrollView {
            VStack(spacing: 20) {
                Toggle("Avisos en la demo", isOn: $store.notificationsEnabled).bankPanel()
                if let notices = store.data?.notices {
                    ForEach(notices) { notice in
                        HStack(alignment: .top, spacing: 14) {
                            Image(systemName: notice.symbol).foregroundStyle(DETheme.blue).frame(width: 42, height: 42).background(DETheme.paleBlue, in: Circle())
                            VStack(alignment: .leading, spacing: 6) { Text(notice.title).font(.headline); Text(notice.detail).font(.subheadline).foregroundStyle(DETheme.muted) }
                            Spacer(minLength: 0)
                        }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
                        Divider()
                    }
                }
                Text(store.notificationsEnabled ? "Avisos simulados activados. No se solicitan permisos push." : "Avisos simulados desactivados. El historial se conserva.")
                    .font(.caption).foregroundStyle(DETheme.muted)
            }.padding(20)
        }.bankScreen("Notificaciones")
    }
}

struct LimitsView: View {
    @Environment(BankStore.self) private var store
    var cardID = "primary"
    @State private var spending = 5000.0
    @State private var withdrawal = 600.0
    @State private var saved = false
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                VStack(alignment: .leading, spacing: 15) {
                    Text("Gasto mensual").font(.headline)
                    MoneyText(amount: Decimal(spending), size: 30, decimals: 0)
                    Slider(value: $spending, in: 500...10000, step: 100).accessibilityLabel("Límite de gasto mensual").accessibilityValue(Money.text(Decimal(spending), decimals: 0))
                    HStack { Text("€ 500"); Spacer(); Text("€ 10.000") }.font(.caption).foregroundStyle(DETheme.muted)
                }.bankPanel()
                VStack(alignment: .leading, spacing: 15) {
                    Text("Retirada diaria").font(.headline)
                    MoneyText(amount: Decimal(withdrawal), size: 30, decimals: 0)
                    Slider(value: $withdrawal, in: 100...1500, step: 50).accessibilityLabel("Límite de retirada diaria").accessibilityValue(Money.text(Decimal(withdrawal), decimals: 0))
                }.bankPanel()
                PrimaryButton(title: "Guardar límites demo") { store.cardLimits[cardID] = spending; store.withdrawalLimit = withdrawal; saved = true }
                DemoFootnote()
            }.padding(20)
        }.bankScreen("Límites")
            .onAppear { spending = store.cardLimits[cardID] ?? 5000; withdrawal = store.withdrawalLimit }
            .alert("Límites guardados", isPresented: $saved) { Button("Aceptar", role: .cancel) { } } message: { Text("Los nuevos límites se aplican a esta sesión demo.") }
    }
}

struct RecurringPaymentsView: View {
    @State private var electricity = true
    @State private var internet = true
    var body: some View {
        Form {
            Section("Pagos recurrentes demo") {
                Toggle(isOn: $electricity) { VStack(alignment: .leading, spacing: 5) { Text("Electricidad"); Text("€ 54,80 · Día 5 de cada mes").font(.caption).foregroundStyle(DETheme.muted) } }
                Toggle(isOn: $internet) { VStack(alignment: .leading, spacing: 5) { Text("Internet"); Text("€ 39,90 · Día 12 de cada mes").font(.caption).foregroundStyle(DETheme.muted) } }
            }
            Section { Text("Puedes activar o pausar estas domiciliaciones ficticias. No se emiten cargos.").font(.footnote) }
        }.bankScreen("Domiciliaciones")
    }
}

struct DocumentsView: View {
    @Environment(BankStore.self) private var store
    var body: some View {
        List {
            Section("Extractos") {
                if let data = store.data {
                    ShareLink(item: DemoStatement(csv: ActivityViewModel().csv(data.transactions.filter { $0.accountID == "personal" })), preview: SharePreview("Extracto demo · Marzo 2024")) {
                        MenuRow(title: "Marzo 2024", symbol: "doc.text", detail: "DEMO")
                    }
                }
            }
            Section("Información") {
                NavigationLink { DemoInformationView(title: "Certificado de titularidad", symbol: "doc.text", message: "Ana García · Cuenta personal · EUR\nES00 0000 0000 0000 0000 0001\n\nDocumento de muestra sin validez bancaria o legal.") } label: { MenuRow(title: "Titularidad de cuenta", symbol: "person.text.rectangle") }
            }
        }.bankScreen("Documentos")
    }
}

struct SecurityView: View {
    @Environment(BankStore.self) private var store
    var body: some View {
        @Bindable var store = store
        Form {
            Section("Alertas demo") {
                Toggle("Saldo bajo", isOn: $store.lowBalanceAlerts)
                Toggle("Movimientos sospechosos", isOn: $store.suspiciousActivityAlerts)
            }
            Section("Verificación de tarjeta") {
                Label("Verificación simulada", systemImage: "checkmark.shield")
                Text("La consulta de tarjeta pide una confirmación demo. La autenticación real se integrará con el backend y los mecanismos seguros de iOS.").font(.footnote)
            }
            Section("Privacidad") { Text("Esta versión utiliza datos ficticios en memoria. No solicita credenciales, no conecta con bancos y no transmite datos.").font(.footnote) }
        }.bankScreen("Seguridad")
    }
}

struct AccountDetailView: View {
    @Environment(\.dismiss) private var dismiss
    let account: BankAccount
    var showsClose = false
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text(account.name).font(.title2.bold())
                MoneyText(amount: account.balance, size: 36)
                VStack(alignment: .leading, spacing: 20) {
                    LabeledContent("Titular", value: account.holder)
                    LabeledContent("Divisa", value: account.currency)
                    Text("Número de cuenta demo").font(.caption).foregroundStyle(DETheme.muted)
                    Text(account.iban).font(.subheadline.monospaced()).textSelection(.enabled)
                }.bankPanel()
                NavigationLink { ActivityView(accountID: account.id) } label: { MenuRow(title: "Historial de cuenta", symbol: "clock") }
                ShareLink(item: "Cuenta DEMO, no válida: " + account.iban) { Label("Compartir datos demo", systemImage: "square.and.arrow.up") }
                DemoFootnote()
            }.padding(20)
        }.bankScreen("Datos de cuenta")
            .toolbar { if showsClose { ToolbarItem(placement: .confirmationAction) { Button("Cerrar") { dismiss() } } } }
    }
}

struct DemoInformationView: View {
    @Environment(\.dismiss) private var dismiss
    let title: String
    let symbol: String
    let message: String
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Image(systemName: symbol).font(.system(size: 52)).foregroundStyle(DETheme.blue)
                Text(message).multilineTextAlignment(.center).foregroundStyle(DETheme.muted)
                DemoFootnote()
            }.padding(30)
        }.bankScreen(title).toolbar { ToolbarItem(placement: .confirmationAction) { Button("Cerrar") { dismiss() } } }
    }
}
