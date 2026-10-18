import ImageIO
import SwiftUI
import UIKit

/// Loads sticker images from the bundle. Images are downsampled off the main thread
/// to the size they are shown at, and kept in memory for fast scrolling.
final class StickerImageLoader: @unchecked Sendable {
    static let shared = StickerImageLoader()

    private let cache = NSCache<NSString, UIImage>()

    func cachedImage(for sticker: Sticker, maxPixel: Int) -> UIImage? {
        cache.object(forKey: key(sticker, maxPixel))
    }

    func image(for sticker: Sticker, maxPixel: Int) async -> UIImage? {
        if let hit = cachedImage(for: sticker, maxPixel: maxPixel) { return hit }
        guard let url = sticker.pngURL else { return nil }
        let image = await Task.detached(priority: .userInitiated) {
            Self.downsample(url: url, maxPixel: maxPixel)
        }.value
        if let image { cache.setObject(image, forKey: key(sticker, maxPixel)) }
        return image
    }

    private func key(_ sticker: Sticker, _ maxPixel: Int) -> NSString {
        "\(sticker.id)@\(maxPixel)" as NSString
    }

    private static func downsample(url: URL, maxPixel: Int) -> UIImage? {
        let sourceOptions = [kCGImageSourceShouldCache: false] as CFDictionary
        guard let source = CGImageSourceCreateWithURL(url as CFURL, sourceOptions) else { return nil }
        let options = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceShouldCacheImmediately: true,
            kCGImageSourceThumbnailMaxPixelSize: maxPixel,
        ] as CFDictionary
        guard let cgImage = CGImageSourceCreateThumbnailAtIndex(source, 0, options) else { return nil }
        return UIImage(cgImage: cgImage)
    }
}

/// Shows a sticker image that fills the space it is given.
struct StickerImageView: View {
    let sticker: Sticker
    var maxPixel = 360

    @State private var image: UIImage?

    var body: some View {
        Group {
            if let image = image ?? StickerImageLoader.shared.cachedImage(for: sticker, maxPixel: maxPixel) {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
            } else {
                Color.clear
            }
        }
        .task(id: sticker.id) {
            image = await StickerImageLoader.shared.image(for: sticker, maxPixel: maxPixel)
        }
        .accessibilityLabel(sticker.name)
    }
}
