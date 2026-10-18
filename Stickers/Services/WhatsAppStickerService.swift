import UIKit

/// Adds a sticker pack to WhatsApp using WhatsApp's official iOS interface:
/// the pack is placed on the pasteboard as JSON and WhatsApp is opened with
/// `whatsapp://stickerPack`. Reference: https://github.com/WhatsApp/stickers/tree/main/iOS
enum WhatsAppStickerService {
    enum ImportError: LocalizedError {
        case whatsAppNotInstalled
        case invalidPack(String)

        var errorDescription: String? {
            switch self {
            case .whatsAppNotInstalled:
                return "WhatsApp is not installed on this device. Install WhatsApp, then try again. You can still copy any sticker and paste it in a chat."
            case .invalidPack(let reason):
                return "This pack could not be prepared for WhatsApp. \(reason)"
            }
        }
    }

    /// Set these once the app is live, so people who receive a sticker can find the app.
    static let iOSAppStoreLink: String? = nil
    static let androidPlayStoreLink: String? = nil

    private static let pasteboardType = "net.whatsapp.third-party.sticker-pack"
    private static let importURL = URL(string: "whatsapp://stickerPack")!
    private static let schemeURL = URL(string: "whatsapp://")!
    private static let pasteboardLifetime: TimeInterval = 60

    // WhatsApp limits (WhatsApp sample app, Limits.swift).
    private static let stickerCountRange = 3...30
    private static let maxStickerBytes = 100 * 1024
    private static let maxTrayBytes = 50 * 1024
    private static let maxEmojis = 3
    private static let maxAccessibilityCharacters = 125

    @MainActor
    static var isWhatsAppInstalled: Bool {
        UIApplication.shared.canOpenURL(schemeURL)
    }

    @MainActor
    static func add(_ pack: StickerPack, publisher: String) async throws {
        guard isWhatsAppInstalled else { throw ImportError.whatsAppNotInstalled }
        let data = try await Task.detached(priority: .userInitiated) {
            try WhatsAppStickerService.payload(for: pack, publisher: publisher)
        }.value
        UIPasteboard.general.setItems(
            [[pasteboardType: data]],
            options: [.localOnly: true, .expirationDate: Date().addingTimeInterval(pasteboardLifetime)])
        _ = await UIApplication.shared.open(importURL)
    }

    /// Builds the JSON payload WhatsApp expects. Sticker images are WebP, the tray icon is PNG.
    static func payload(for pack: StickerPack, publisher: String) throws -> Data {
        guard stickerCountRange.contains(pack.stickers.count) else {
            throw ImportError.invalidPack("A pack needs 3 to 30 stickers.")
        }
        guard let trayURL = pack.trayURL, let tray = try? Data(contentsOf: trayURL), tray.count <= maxTrayBytes else {
            throw ImportError.invalidPack("The tray icon is missing or too large.")
        }

        let stickers: [[String: Any]] = try pack.stickers.map { sticker -> [String: Any] in
            guard let url = sticker.webpURL, let image = try? Data(contentsOf: url), image.count <= maxStickerBytes else {
                throw ImportError.invalidPack("“\(sticker.name)” is missing or too large.")
            }
            return [
                "image_data": image.base64EncodedString(),
                "emojis": Array(sticker.emojis.prefix(maxEmojis)),
                "accessibility_text": String(sticker.accessibilityText.prefix(maxAccessibilityCharacters)),
            ]
        }

        var json: [String: Any] = [
            "identifier": identifier(for: pack),
            "name": pack.title,
            "publisher": publisher,
            "tray_image": tray.base64EncodedString(),
            "stickers": stickers,
        ]
        if let link = iOSAppStoreLink { json["ios_app_store_link"] = link }
        if let link = androidPlayStoreLink { json["android_play_store_link"] = link }
        return try JSONSerialization.data(withJSONObject: json)
    }

    /// Allowed characters: a-z, A-Z, 0-9, "_", "-", "." and space. Max 128 characters.
    private static func identifier(for pack: StickerPack) -> String {
        let base = Bundle.main.bundleIdentifier ?? "stickers"
        return String("\(base).\(pack.id)".prefix(128))
    }
}

/// Runs a WhatsApp import from a view and keeps its error for an alert.
@MainActor
final class WhatsAppImporter: ObservableObject {
    @Published var errorMessage: String?
    @Published private(set) var isWorking = false

    func add(_ pack: StickerPack) {
        guard !isWorking else { return }
        isWorking = true
        Task {
            defer { isWorking = false }
            do {
                try await WhatsAppStickerService.add(pack, publisher: StickerCatalog.shared.publisher)
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}
