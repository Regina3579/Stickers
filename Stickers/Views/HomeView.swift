import SwiftUI

/// Landing page: hero banner, search and one card per sticker category.
struct HomeView: View {
    @State private var query = ""
    @FocusState private var isSearching: Bool

    private let catalog = StickerCatalog.shared
    private var trimmedQuery: String { query.trimmingCharacters(in: .whitespacesAndNewlines) }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                HeroHeader()

                SearchField(text: $query, isFocused: $isSearching)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 4)

                if trimmedQuery.isEmpty {
                    ForEach(catalog.packs) { pack in
                        CategoryCard(pack: pack)
                    }
                } else {
                    SearchResultsView(query: trimmedQuery)
                }

                Image("CloudsFooter")
                    .resizable()
                    .scaledToFit()
                    .accessibilityHidden(true)
            }
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Theme.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
    }
}

/// Girl, puppy and the "Stickers" title from the design.
private struct HeroHeader: View {
    var body: some View {
        Image("Hero")
            .resizable()
            .scaledToFit()
            .mask(
                LinearGradient(stops: [.init(color: .black, location: 0.82),
                                       .init(color: .black.opacity(0), location: 1)],
                               startPoint: .top, endPoint: .bottom))
            .accessibilityLabel("Stickers. Express more with cute stickers.")
    }
}

private struct SearchField: View {
    @Binding var text: String
    var isFocused: FocusState<Bool>.Binding

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 20, weight: .semibold))
                .foregroundStyle(Theme.searchPlaceholder)
            TextField("Search stickers...", text: $text)
                .font(Theme.rounded(.body, .medium))
                .foregroundStyle(Theme.ink)
                .focused(isFocused)
                .submitLabel(.search)
                .autocorrectionDisabled()
            if !text.isEmpty {
                Button {
                    text = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(Theme.searchPlaceholder.opacity(0.6))
                }
                .accessibilityLabel("Clear search")
            }
        }
        .padding(.horizontal, 20)
        .frame(height: 54)
        .background(.white, in: Capsule())
        .overlay(Capsule().stroke(Color(hex: "#E7D9FF"), lineWidth: 1.5))
        .shadow(color: Color(hex: "#B38CF0").opacity(0.25), radius: 12, y: 5)
    }
}

private struct SearchResultsView: View {
    let query: String
    private let catalog = StickerCatalog.shared

    var body: some View {
        let packs = catalog.packs.filter { $0.title.localizedCaseInsensitiveContains(query) }
        let stickers = catalog.search(query)

        VStack(alignment: .leading, spacing: 16) {
            ForEach(packs) { pack in
                CategoryCard(pack: pack)
            }

            if !stickers.isEmpty {
                Text("\(stickers.count) sticker\(stickers.count == 1 ? "" : "s")")
                    .font(Theme.rounded(.headline))
                    .foregroundStyle(Theme.ink)
                    .padding(.horizontal, 20)
                StickerGrid(stickers: stickers)
                    .padding(.horizontal, 16)
            }

            if packs.isEmpty && stickers.isEmpty {
                VStack(spacing: 10) {
                    Image(systemName: "heart.text.square")
                        .font(.system(size: 44))
                        .foregroundStyle(Theme.accent.opacity(0.7))
                    Text("No stickers found for “\(query)”")
                        .font(Theme.rounded(.headline))
                        .foregroundStyle(Theme.ink)
                    Text("Try love, hug, happy or family.")
                        .font(Theme.rounded(.subheadline, .medium))
                        .foregroundStyle(Theme.secondaryInk)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 40)
            }
        }
    }
}
