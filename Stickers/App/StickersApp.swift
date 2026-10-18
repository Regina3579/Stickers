import SwiftUI

@main
struct StickersApp: App {
    @StateObject private var toast = ToastCenter()

    var body: some Scene {
        WindowGroup {
            NavigationStack {
                HomeView()
                    .navigationDestination(for: StickerPack.self) { pack in
                        PackDetailView(pack: pack)
                    }
            }
            .tint(Theme.accent)
            .overlay(alignment: .bottom) { ToastView() }
            .environmentObject(toast)
        }
    }
}
