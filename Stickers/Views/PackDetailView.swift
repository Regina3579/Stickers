import SwiftUI

/// All stickers of one category, with copy, drag, share and "Add to WhatsApp".
struct PackDetailView: View {
    let pack: StickerPack

    @StateObject private var importer = WhatsAppImporter()
    @State private var showingIMessageHelp = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header
                tip
                StickerGrid(stickers: pack.stickers, wide: pack.wideStickers)
            }
            .padding(16)
        }
        .background(pack.background.ignoresSafeArea())
        .navigationTitle(pack.title)
        .navigationBarTitleDisplayMode(.inline)
        .whatsAppErrorAlert(importer)
        .sheet(isPresented: $showingIMessageHelp) { IMessageHelpSheet() }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 14) {
                Image(pack.banner)
                    .resizable()
                    .scaledToFill()
                    .frame(width: 116, height: 82)
                    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    Text(pack.title)
                        .font(Theme.rounded(.title2))
                        .foregroundStyle(Theme.ink)
                    Text(pack.subtitle)
                        .font(Theme.rounded(.subheadline, .medium))
                        .foregroundStyle(Theme.secondaryInk)
                    Text("\(pack.stickers.count) stickers")
                        .font(Theme.rounded(.caption, .semibold))
                        .foregroundStyle(pack.tint)
                }
            }

            HStack(spacing: 10) {
                Button {
                    importer.add(pack)
                } label: {
                    Label(importer.isWorking ? "Opening…" : "Add to WhatsApp", systemImage: "plus.bubble.fill")
                        .font(Theme.rounded(.subheadline))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .foregroundStyle(.white)
                        .background(Color(hex: "#25D366"), in: Capsule())
                }
                .disabled(importer.isWorking)

                Button {
                    showingIMessageHelp = true
                } label: {
                    Label("iMessage", systemImage: "message.fill")
                        .font(Theme.rounded(.subheadline))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .foregroundStyle(.white)
                        .background(Color(hex: "#2F8CFF"), in: Capsule())
                }
            }
        }
        .padding(16)
        .background(.white.opacity(0.6), in: RoundedRectangle(cornerRadius: 26, style: .continuous))
    }

    private var tip: some View {
        Label {
            Text("**Tap** a sticker to copy it, then paste it in any chat. **Touch and hold** to drag it into another app or to share it.")
                .font(Theme.rounded(.footnote, .medium))
                .foregroundStyle(Theme.secondaryInk)
        } icon: {
            Image(systemName: "hand.tap.fill")
                .foregroundStyle(pack.tint)
        }
        .padding(.horizontal, 4)
    }
}
