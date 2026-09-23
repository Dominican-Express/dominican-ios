import SwiftUI

struct ContactPicker: View {
    let contacts: [Contact]
    @Binding var selected: Contact?
    var showsNew = false
    var onNew: (() -> Void)?
    var body: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 4), spacing: 14) {
            ForEach(contacts) { contact in
                Button { selected = contact } label: {
                    VStack(spacing: 4) {
                        AvatarView(initial: contact.initial, selected: selected?.id == contact.id)
                        Text(contact.name).font(.caption).foregroundStyle(DETheme.ink)
                    }.frame(maxWidth: .infinity)
                }.buttonStyle(.plain).accessibilityLabel(contact.name).accessibilityAddTraits(selected?.id == contact.id ? .isSelected : [])
            }
            if showsNew {
                Button { onNew?() } label: {
                    VStack(spacing: 4) { AvatarView(initial: "+"); Text("Nuevo").font(.caption).foregroundStyle(DETheme.ink) }
                }.buttonStyle(.plain).accessibilityLabel("Elegir otro contacto demo")
            }
        }
    }
}

struct ContactListView: View {
    @Environment(\.dismiss) private var dismiss
    let contacts: [Contact]
    let select: (Contact) -> Void
    @State private var query = ""
    var body: some View {
        List(contacts.filter { query.isEmpty || $0.name.localizedStandardContains(query) }) { contact in
            Button { select(contact); dismiss() } label: {
                HStack { AvatarView(initial: contact.initial, size: 40); Text(contact.name); Spacer(); Image(systemName: "chevron.right") }
            }
        }.searchable(text: $query, prompt: "Buscar contacto demo")
            .bankScreen("Contactos").toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cerrar") { dismiss() } } }
    }
}
