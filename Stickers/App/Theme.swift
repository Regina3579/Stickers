import SwiftUI

/// Colors and fonts taken from the landing page design.
enum Theme {
    static let accent = Color(hex: "#E2559C")
    static let ink = Color(hex: "#4A2E3B")
    static let secondaryInk = Color(hex: "#8A6F86")
    static let searchPlaceholder = Color(hex: "#7E73A8")

    /// Starts with the lavender sky at the top of the hero picture, fades to soft pink.
    static let background = LinearGradient(
        stops: [.init(color: Color(hex: "#C9BEF5"), location: 0),
                .init(color: Color(hex: "#ECD3F6"), location: 0.3),
                .init(color: Color(hex: "#FBEFF8"), location: 0.6),
                .init(color: Color(hex: "#FCEAF4"), location: 1)],
        startPoint: .top, endPoint: .bottom)

    static func rounded(_ style: Font.TextStyle, _ weight: Font.Weight = .bold) -> Font {
        .system(style, design: .rounded).weight(weight)
    }
}
