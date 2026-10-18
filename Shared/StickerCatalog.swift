import Foundation
import SwiftUI

/// One sticker. Its images live in the bundled `StickerLibrary` folder:
/// `png/<id>.png` (copy, drag, iMessage) and `webp/<id>.webp` (WhatsApp).
struct Sticker: Decodable, Identifiable, Hashable, Sendable {
    let id: String
    let name: String
    let emojis: [String]
    let keywords: [String]
    let accessibilityText: String

    var pngURL: URL? { StickerCatalog.libraryURL(for: "png/\(id).png") }
    var webpURL: URL? { StickerCatalog.libraryURL(for: "webp/\(id).webp") }

    func matches(_ query: String) -> Bool {
        let q = query.lowercased()
        return name.lowercased().contains(q)
            || keywords.contains { $0.hasPrefix(q) }
            || emojis.contains(query)
    }
}

/// A category such as "Love" or "Friendship". Each pack is also one WhatsApp sticker pack.
struct StickerPack: Decodable, Identifiable, Hashable, Sendable {
    struct Colors: Decodable, Hashable, Sendable {
        let tint: String
        let top: String
        let bottom: String
    }

    let id: String
    let title: String
    let subtitle: String
    let banner: String
    let colors: Colors
    let stickers: [Sticker]

    var trayURL: URL? { StickerCatalog.libraryURL(for: "tray/\(id).png") }
    var tint: Color { Color(hex: colors.tint) }
    var background: LinearGradient {
        LinearGradient(colors: [Color(hex: colors.top), Color(hex: colors.bottom)],
                       startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    static func == (lhs: StickerPack, rhs: StickerPack) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }
}

/// The full sticker library, decoded once from `StickerLibrary/catalog.json`.
struct StickerCatalog: Decodable, Sendable {
    let publisher: String
    let packs: [StickerPack]

    static let libraryFolder = "StickerLibrary"

    static let shared: StickerCatalog = {
        guard let url = libraryURL(for: "catalog.json"),
              let data = try? Data(contentsOf: url),
              let catalog = try? JSONDecoder().decode(StickerCatalog.self, from: data) else {
            assertionFailure("StickerLibrary/catalog.json is missing or invalid")
            return StickerCatalog(publisher: "Stickers", packs: [])
        }
        return catalog
    }()

    static func libraryURL(for relativePath: String) -> URL? {
        let url = Bundle.main.bundleURL
            .appendingPathComponent(libraryFolder)
            .appendingPathComponent(relativePath)
        return FileManager.default.fileExists(atPath: url.path) ? url : nil
    }

    func search(_ query: String) -> [Sticker] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return [] }
        return packs.flatMap(\.stickers).filter { $0.matches(q) }
    }
}

extension Color {
    /// Creates a color from a `#RRGGBB` string.
    init(hex: String) {
        let value = UInt64(hex.trimmingCharacters(in: CharacterSet(charactersIn: "#")), radix: 16) ?? 0
        self.init(red: Double((value >> 16) & 0xFF) / 255,
                  green: Double((value >> 8) & 0xFF) / 255,
                  blue: Double(value & 0xFF) / 255)
    }
}
