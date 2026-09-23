import SwiftUI

struct SharedAccountView: View {
    @Environment(BankStore.self) private var store
    @State private var showsInvite = false
    @State private var showsSettings = false
    @State private var invitedName: String?
    var body: some View {
        ScrollView {
            if let data = store.data, let account = data.accounts.first(where: { $0.id == "shared" }) {
                VStack(alignment: .leading, spacing: 22) {
                    VStack(alignment: .leading, spacing: 20) {
                        HStack(spacing: 14) {
                            Image(systemName: "person.2.fill").font(.title2).foregroundStyle(DETheme.blue).frame(width: 60, height: 60).background(DETheme.paleBlue, in: Circle())
                            VStack(alignment: .leading, spacing: 5) { Text("Cuenta compartida").font(.title3.bold()); Text("Ana, Carlos y Marta").font(.subheadline).foregroundStyle(DETheme.muted) }
                        }
                        MoneyText(amount: account.balance, size: 31)
                        HStack(spacing: -8) { ForEach(data.members) { AvatarView(initial: $0.initial, size: 36).overlay(Circle().stroke(DETheme.background, lineWidth: 2)) } }
                    }.frame(maxWidth: .infinity, alignment: .leading).bankPanel()
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Titulares y permisos").font(.headline).padding(.bottom, 8)
                        ForEach(data.members + store.extraMembers) { member in
                            NavigationLink { MemberDetailView(member: member) } label: {
                                HStack {
                                    AvatarView(initial: member.initial, size: 38)
                                    Text(member.name).font(.subheadline)
                                    Spacer()
                                    Text(store.memberRoles[member.id] ?? member.role).font(.caption).foregroundStyle(DETheme.muted)
                                    Image(systemName: "chevron.right").font(.caption)
                                }.padding(.vertical, 6)
                            }.buttonStyle(.plain)
                            Divider()
                        }
                    }
                    Button { showsInvite = true } label: {
                        Label("Invitar a un nuevo titular", systemImage: "person.badge.plus").font(.subheadline).frame(maxWidth: .infinity, alignment: .leading).padding(18).background(DETheme.paleBlue, in: RoundedRectangle(cornerRadius: 12))
                    }
                    NavigationLink { ActivityView(accountID: account.id) } label: { MenuRow(title: "Movimientos compartidos", symbol: "clock") }
                    DemoFootnote()
                }.padding(20)
                .sheet(isPresented: $showsInvite) {
                    NavigationStack {
                        let ids = Set((data.members + store.extraMembers).map(\.id))
                        ContactListView(contacts: data.contacts.filter { !ids.contains($0.id) }) { contact in
                            store.extraMembers.append(AccountMember(id: contact.id, name: contact.name, role: "Invitación demo"))
                            invitedName = contact.name
                        }
                    }
                }
                .sheet(isPresented: $showsSettings) { NavigationStack { AccountDetailView(account: account, showsClose: true) } }
            }
        }.bankScreen("Cuenta compartida")
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { showsSettings = true } label: { Image(systemName: "gearshape") }.accessibilityLabel("Configuración de cuenta compartida") } }
            .alert("Invitación simulada", isPresented: Binding(get: { invitedName != nil }, set: { if !$0 { invitedName = nil } })) { Button("Aceptar") { invitedName = nil } } message: { Text("Se ha añadido a \(invitedName ?? "el contacto") a la demo. No se ha enviado ninguna invitación real.") }
    }
}

struct MemberDetailView: View {
    @Environment(BankStore.self) private var store
    let member: AccountMember
    var body: some View {
        Form {
            Section { HStack { AvatarView(initial: member.initial); Text(member.name).font(.headline) } }
            Section("Permisos demo") {
                if member.id == "a" { LabeledContent("Rol", value: "Administradora") }
                else {
                    Picker("Rol", selection: Binding(get: { store.memberRoles[member.id] ?? member.role }, set: { store.memberRoles[member.id] = $0 })) {
                        Text("Puede gastar").tag("Puede gastar")
                        Text("Solo consulta").tag("Solo consulta")
                        if member.role == "Invitación demo" { Text("Invitación demo").tag("Invitación demo") }
                    }
                }
            }
            Section { Text("Los cambios solo afectan a esta sesión de demostración.").font(.footnote) }
        }.bankScreen("Titular")
    }
}
