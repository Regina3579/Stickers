import SwiftUI

/// Small message shown at the bottom of the screen, e.g. after copying a sticker.
@MainActor
final class ToastCenter: ObservableObject {
    struct Toast: Equatable {
        let id = UUID()
        let icon: String
        let message: String
    }

    @Published private(set) var current: Toast?
    private var hideTask: Task<Void, Never>?

    func show(_ message: String, icon: String = "checkmark.circle.fill") {
        current = Toast(icon: icon, message: message)
        hideTask?.cancel()
        hideTask = Task {
            try? await Task.sleep(nanoseconds: 2_200_000_000)
            guard !Task.isCancelled else { return }
            current = nil
        }
    }
}

struct ToastView: View {
    @EnvironmentObject private var center: ToastCenter

    var body: some View {
        ZStack {
            if let toast = center.current {
                HStack(spacing: 10) {
                    Image(systemName: toast.icon)
                        .foregroundStyle(Theme.accent)
                    Text(toast.message)
                        .font(Theme.rounded(.subheadline, .semibold))
                        .foregroundStyle(Theme.ink)
                        .multilineTextAlignment(.leading)
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
                .background(.white, in: Capsule())
                .shadow(color: Theme.accent.opacity(0.25), radius: 14, y: 6)
                .padding(.horizontal, 24)
                .padding(.bottom, 12)
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .id(toast.id)
                .accessibilityAddTraits(.isStaticText)
            }
        }
        .animation(.spring(response: 0.35, dampingFraction: 0.8), value: center.current)
        .allowsHitTesting(false)
    }
}
