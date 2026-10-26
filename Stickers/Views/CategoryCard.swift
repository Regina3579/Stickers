import SwiftUI

/// One category row on the landing page: picture, title, sticker preview and "+" button.
/// The picture and the sticker previews share one height, so they read as one row.
struct CategoryCard: View {
    let pack: StickerPack

    static let tileHeight: CGFloat = 56

    @StateObject private var importer = WhatsAppImporter()
    @State private var showingIMessageHelp = false

    /// "Self-Love & Self-Care" -> "Self-Love &" / "Self-Care", "Two Words" -> "Two" / "Words":
    /// short lines leave more room for the sticker previews.
    private var shortLinesTitle: String {
        pack.title.contains(" & ")
            ? pack.title.replacingOccurrences(of: " & ", with: " &\n")
            : pack.title.replacingOccurrences(of: " ", with: "\n")
    }

    var body: some View {
        ZStack(alignment: .trailing) {
            NavigationLink(value: pack) {
                HStack(spacing: 8) {
                    Image(pack.banner)
                        .resizable()
                        .scaledToFill()
                        .frame(width: Self.tileHeight, height: Self.tileHeight)
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                        .accessibilityHidden(true)

                    Text(shortLinesTitle)
                        .font(Theme.rounded(.subheadline))
                        .foregroundStyle(Theme.ink)
                        .multilineTextAlignment(.leading)
                        .fixedSize()

                    Capsule()
                        .fill(pack.tint.opacity(0.25))
                        .frame(width: 1.5, height: Self.tileHeight - 8)

                    PreviewStrip(stickers: pack.stickers, wide: pack.wideStickers, height: Self.tileHeight)

                    Spacer(minLength: 36)   // room for the "+" button
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    RoundedRectangle(cornerRadius: 26, style: .continuous)
                        .fill(pack.background)
                        .overlay(RoundedRectangle(cornerRadius: 26, style: .continuous)
                            .stroke(.white.opacity(0.9), lineWidth: 1.5))
                        .shadow(color: pack.tint.opacity(0.18), radius: 10, y: 4))
            }
            .buttonStyle(PressableStyle())
            .accessibilityLabel("\(pack.title), \(pack.stickers.count) stickers")
            .accessibilityHint("Opens the category")

            Menu {
                Button {
                    importer.add(pack)
                } label: {
                    Label("Add to WhatsApp", systemImage: "plus.bubble")
                }
                Button {
                    showingIMessageHelp = true
                } label: {
                    Label("Use in iMessage", systemImage: "message")
                }
            } label: {
                PlusBadge(tint: pack.tint, isWorking: importer.isWorking)
            }
            .padding(.trailing, 12)
            .accessibilityLabel("Add \(pack.title) stickers")
        }
        .padding(.horizontal, 16)
        .whatsAppErrorAlert(importer)
        .sheet(isPresented: $showingIMessageHelp) { IMessageHelpSheet() }
    }
}

/// Sticker previews as tall as the category picture. Shows as many as fit the width.
/// Wide stickers get wide tiles; the empty space above and below them is cropped.
private struct PreviewStrip: View {
    let stickers: [Sticker]
    let wide: Bool
    let height: CGFloat

    var body: some View {
        ViewThatFits(in: .horizontal) {
            strip(3)
            strip(2)
            strip(1)
        }
        .accessibilityHidden(true)
    }

    private func strip(_ count: Int) -> some View {
        HStack(spacing: 6) {
            ForEach(stickers.prefix(count)) { sticker in
                Color.clear
                    .frame(width: wide ? height * 1.4 : height, height: height)
                    .overlay(StickerImageView(sticker: sticker, maxPixel: 300, fill: wide))
                    .clipped()
            }
        }
    }
}

struct PlusBadge: View {
    let tint: Color
    var isWorking = false

    var body: some View {
        ZStack {
            Circle()
                .fill(LinearGradient(colors: [tint.opacity(0.85), tint],
                                     startPoint: .top, endPoint: .bottom))
                .overlay(Circle().stroke(.white.opacity(0.8), lineWidth: 2))
                .shadow(color: tint.opacity(0.35), radius: 6, y: 3)
            if isWorking {
                ProgressView().tint(.white)
            } else {
                Image(systemName: "plus")
                    .font(.system(size: 19, weight: .bold))
                    .foregroundStyle(.white)
            }
        }
        .frame(width: 40, height: 40)
    }
}

struct PressableStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.spring(response: 0.25, dampingFraction: 0.7), value: configuration.isPressed)
    }
}

/// Shows the error of a failed "Add to WhatsApp".
private struct WhatsAppErrorAlert: ViewModifier {
    @ObservedObject var importer: WhatsAppImporter

    func body(content: Content) -> some View {
        content.alert("Couldn’t add to WhatsApp", isPresented: $importer.showingError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(importer.errorMessage)
        }
    }
}

extension View {
    @MainActor
    func whatsAppErrorAlert(_ importer: WhatsAppImporter) -> some View {
        modifier(WhatsAppErrorAlert(importer: importer))
    }
}
