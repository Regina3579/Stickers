import CoreTransferable
import UIKit
import UniformTypeIdentifiers

/// Copy, drag and share for a single sticker. The bundled PNG keeps its transparent
/// background, so apps that accept images (WhatsApp, iMessage, Instagram, Telegram...)
/// receive the sticker exactly as it looks here.
extension Sticker {
    var pngData: Data? {
        pngURL.flatMap { try? Data(contentsOf: $0) }
    }

    /// Puts the sticker on the clipboard as PNG. Returns `false` if the file is missing.
    @discardableResult
    func copyToClipboard() -> Bool {
        guard let data = pngData else { return false }
        UIPasteboard.general.setData(data, forPasteboardType: UTType.png.identifier)
        return true
    }

    /// Item provider used for drag and drop into other apps.
    func dragItemProvider() -> NSItemProvider {
        let provider = NSItemProvider()
        provider.suggestedName = name
        if let url = pngURL {
            provider.registerDataRepresentation(forTypeIdentifier: UTType.png.identifier,
                                                visibility: .all) { completion in
                do {
                    completion(try Data(contentsOf: url), nil)
                } catch {
                    completion(nil, error)
                }
                return nil
            }
        }
        return provider
    }
}

/// Lets `ShareLink` send a sticker as a PNG image.
struct StickerShareItem: Transferable {
    let sticker: Sticker

    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(exportedContentType: .png) { item in
            guard let data = item.sticker.pngData else { throw CocoaError(.fileNoSuchFile) }
            return data
        }
    }
}
