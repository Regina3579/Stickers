import SwiftUI
import UIKit

/// Grid of sticker tiles. Wide stickers get wider tiles: 2 per row on iPhone instead of 3.
struct StickerGrid: View {
    let stickers: [Sticker]
    var wide = false

    private var columns: [GridItem] {
        [wide ? GridItem(.adaptive(minimum: 150, maximum: 260), spacing: 12)
              : GridItem(.adaptive(minimum: 96, maximum: 150), spacing: 12)]
    }

    var body: some View {
        LazyVGrid(columns: columns, spacing: 12) {
            ForEach(stickers) { sticker in
                StickerTile(sticker: sticker, wide: wide)
            }
        }
    }
}

/// One sticker. Tap copies it, touch and hold shows a menu, and it can be dragged
/// straight into WhatsApp, iMessage or any app that accepts images.
struct StickerTile: View {
    let sticker: Sticker
    var wide = false

    @EnvironmentObject private var toast: ToastCenter
    @State private var showingPreview = false

    var body: some View {
        // A wide sticker fills the full tile width; the empty space above and below it is cropped.
        Color.clear
            .aspectRatio(wide ? 4 / 3 : 1, contentMode: .fit)
            .overlay(StickerImageView(sticker: sticker, maxPixel: wide ? 512 : 360, fill: wide))
            .clipped()
            .padding(wide ? 4 : 8)
            .frame(maxWidth: .infinity)
            .background(.white.opacity(0.75), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).stroke(.white, lineWidth: 1.5))
            .contentShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
            .onTapGesture(perform: copy)
            .onDrag { sticker.dragItemProvider() }
            .contextMenu {
                Button(action: copy) {
                    Label("Copy", systemImage: "doc.on.doc")
                }
                ShareLink(item: StickerShareItem(sticker: sticker),
                          preview: SharePreview(sticker.name, image: sticker.previewImage)) {
                    Label("Share…", systemImage: "square.and.arrow.up")
                }
                Button {
                    showingPreview = true
                } label: {
                    Label("Preview", systemImage: "eye")
                }
            }
            .sheet(isPresented: $showingPreview) {
                StickerPreviewSheet(sticker: sticker)
                    .environmentObject(toast)
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(sticker.name)
            .accessibilityAddTraits(.isButton)
            .accessibilityHint("Copies the sticker")
    }

    @MainActor
    private func copy() {
        if sticker.copyToClipboard() {
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            toast.show("Copied! Paste it in WhatsApp, iMessage or any chat.")
        } else {
            toast.show("Sorry, this sticker could not be copied.", icon: "exclamationmark.triangle.fill")
        }
    }
}

/// Large view of one sticker.
struct StickerPreviewSheet: View {
    let sticker: Sticker

    @EnvironmentObject private var toast: ToastCenter
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 20) {
            StickerImageView(sticker: sticker, maxPixel: 1024)
                .frame(maxWidth: 260, maxHeight: 260)
                .onDrag { sticker.dragItemProvider() }
                .padding(.top, 28)

            Text(sticker.name)
                .font(Theme.rounded(.title3))
                .foregroundStyle(Theme.ink)

            HStack(spacing: 12) {
                Button {
                    if sticker.copyToClipboard() {
                        UINotificationFeedbackGenerator().notificationOccurred(.success)
                        toast.show("Copied! Paste it in WhatsApp, iMessage or any chat.")
                        dismiss()
                    }
                } label: {
                    Label("Copy", systemImage: "doc.on.doc.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)

                ShareLink(item: StickerShareItem(sticker: sticker),
                          preview: SharePreview(sticker.name, image: sticker.previewImage)) {
                    Label("Share", systemImage: "square.and.arrow.up")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            }
            .controlSize(.large)
            .font(Theme.rounded(.headline))
            .padding(.horizontal, 24)

            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity)
        .background(Theme.background.ignoresSafeArea())
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
    }
}

private extension Sticker {
    /// Image shown in the share sheet header.
    var previewImage: Image {
        let image = pngURL.flatMap { UIImage(contentsOfFile: $0.path) } ?? UIImage()
        return Image(uiImage: image)
    }
}
