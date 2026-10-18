import SwiftUI

/// Explains how to use the Stickers iMessage app that ships inside this app.
struct IMessageHelpSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    private let steps: [(icon: String, text: String)] = [
        ("message.fill", "Open **Messages** and any chat."),
        ("plus.circle.fill", "Tap **+** next to the text box, then tap **More** and choose **Stickers**."),
        ("hand.tap.fill", "Tap a sticker to add it to your message, or **touch, hold and drag** it onto a chat bubble."),
        ("doc.on.doc.fill", "Or simply copy any sticker in this app and paste it into the chat."),
    ]

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 18) {
                ForEach(steps.indices, id: \.self) { index in
                    HStack(alignment: .top, spacing: 14) {
                        Image(systemName: steps[index].icon)
                            .font(.title3)
                            .foregroundStyle(Theme.accent)
                            .frame(width: 30)
                        Text(LocalizedStringKey(steps[index].text))
                            .font(Theme.rounded(.body, .medium))
                            .foregroundStyle(Theme.ink)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                Spacer(minLength: 0)

                Button {
                    if let url = URL(string: "sms:") { openURL(url) }
                } label: {
                    Label("Open Messages", systemImage: "message.fill")
                        .font(Theme.rounded(.headline))
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            }
            .padding(24)
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Stickers in iMessage")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}
