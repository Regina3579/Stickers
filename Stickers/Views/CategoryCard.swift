import SwiftUI

/// One category row on the landing page: picture, title, sticker preview and "+" button.
struct CategoryCard: View {
    let pack: StickerPack

    @StateObject private var importer = WhatsAppImporter()
    @State private var showingIMessageHelp = false

    var body: some View {
        ZStack(alignment: .trailing) {
            NavigationLink(value: pack) {
                HStack(spacing: 10) {
                    Image(pack.banner)
                        .resizable()
                        .scaledToFill()
                        .frame(width: 92, height: 66)
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                        .accessibilityHidden(true)

                    Text(pack.title)
                        .font(Theme.rounded(.headline))
                        .foregroundStyle(Theme.ink)
                        .multilineTextAlignment(.leading)
                        .lineLimit(2)
                        .minimumScaleFactor(0.85)
                        .fixedSize(horizontal: false, vertical: true)
                        .layoutPriority(1)

                    Capsule()
                        .fill(pack.tint.opacity(0.25))
                        .frame(width: 1.5, height: 48)

                    PreviewStrip(stickers: pack.stickers)

                    Spacer(minLength: 54)   // room for the "+" button
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
            .padding(.trailing, 14)
            .accessibilityLabel("Add \(pack.title) stickers")
        }
        .padding(.horizontal, 16)
        .whatsAppErrorAlert(importer)
        .sheet(isPresented: $showingIMessageHelp) { IMessageHelpSheet() }
    }
}

/// Small overlapping sticker thumbnails. Shows as many as fit the width.
private struct PreviewStrip: View {
    let stickers: [Sticker]

    var body: some View {
        ViewThatFits(in: .horizontal) {
            strip(4)
            strip(3)
            strip(2)
            strip(1)
        }
        .accessibilityHidden(true)
    }

    private func strip(_ count: Int) -> some View {
        HStack(spacing: -4) {
            ForEach(stickers.prefix(count)) { sticker in
                StickerImageView(sticker: sticker, maxPixel: 150)
                    .frame(width: 42, height: 42)
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
                    .font(.system(size: 22, weight: .bold))
                    .foregroundStyle(.white)
            }
        }
        .frame(width: 46, height: 46)
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
