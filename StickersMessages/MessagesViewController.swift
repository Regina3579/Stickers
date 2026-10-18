import Messages
import UIKit

/// The "Stickers" iMessage app. People pick a category, then tap a sticker to add it
/// to their message or touch, hold and drag it onto any chat bubble.
final class MessagesViewController: MSMessagesAppViewController {
    private let catalog = StickerCatalog.shared
    private let browser = PackStickerBrowserViewController(stickerSize: .regular)
    private let chipScrollView = UIScrollView()
    private let chipStack = UIStackView()
    private var chipButtons: [UIButton] = []

    private static let lastPackKey = "lastSelectedPackIndex"

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(hex: "#FBEFFA")
        setUpChips()
        setUpBrowser()
        let saved = UserDefaults.standard.integer(forKey: Self.lastPackKey)
        select(catalog.packs.indices.contains(saved) ? saved : 0)
    }

    private func setUpChips() {
        chipScrollView.showsHorizontalScrollIndicator = false
        chipScrollView.translatesAutoresizingMaskIntoConstraints = false
        chipStack.axis = .horizontal
        chipStack.spacing = 8
        chipStack.translatesAutoresizingMaskIntoConstraints = false

        for (index, pack) in catalog.packs.enumerated() {
            let button = UIButton(configuration: .filled(), primaryAction: UIAction { [weak self] _ in
                self?.select(index)
            })
            button.accessibilityLabel = pack.title
            chipButtons.append(button)
            chipStack.addArrangedSubview(button)
        }

        view.addSubview(chipScrollView)
        chipScrollView.addSubview(chipStack)
        NSLayoutConstraint.activate([
            chipScrollView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 8),
            chipScrollView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            chipScrollView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            chipScrollView.heightAnchor.constraint(equalToConstant: 40),

            chipStack.topAnchor.constraint(equalTo: chipScrollView.contentLayoutGuide.topAnchor),
            chipStack.bottomAnchor.constraint(equalTo: chipScrollView.contentLayoutGuide.bottomAnchor),
            chipStack.leadingAnchor.constraint(equalTo: chipScrollView.contentLayoutGuide.leadingAnchor, constant: 12),
            chipStack.trailingAnchor.constraint(equalTo: chipScrollView.contentLayoutGuide.trailingAnchor, constant: -12),
            chipStack.heightAnchor.constraint(equalTo: chipScrollView.frameLayoutGuide.heightAnchor),
        ])
    }

    private func setUpBrowser() {
        addChild(browser)
        browser.view.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(browser.view)
        NSLayoutConstraint.activate([
            browser.view.topAnchor.constraint(equalTo: chipScrollView.bottomAnchor, constant: 4),
            browser.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            browser.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            browser.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
        browser.didMove(toParent: self)
    }

    private func select(_ index: Int) {
        guard catalog.packs.indices.contains(index) else { return }
        UserDefaults.standard.set(index, forKey: Self.lastPackKey)
        for (i, button) in chipButtons.enumerated() {
            button.configuration = chipConfiguration(for: catalog.packs[i], selected: i == index)
            button.accessibilityTraits = i == index ? [.button, .selected] : .button
        }
        browser.show(catalog.packs[index])
        let chip = chipButtons[index]
        chipScrollView.scrollRectToVisible(chip.frame.insetBy(dx: -24, dy: 0), animated: true)
    }

    private func chipConfiguration(for pack: StickerPack, selected: Bool) -> UIButton.Configuration {
        var config = UIButton.Configuration.filled()
        config.cornerStyle = .capsule
        config.baseBackgroundColor = selected ? UIColor(hex: pack.colors.tint) : .white
        config.baseForegroundColor = selected ? .white : UIColor(hex: "#4A2E3B")
        config.contentInsets = NSDirectionalEdgeInsets(top: 8, leading: 14, bottom: 8, trailing: 14)
        let base = UIFont.systemFont(ofSize: 15, weight: .bold)
        var title = AttributedString(pack.title)
        title.uiKit.font = base.fontDescriptor.withDesign(.rounded).map { UIFont(descriptor: $0, size: 15) } ?? base
        config.attributedTitle = title
        return config
    }
}

/// Apple's sticker browser, fed with the stickers of the selected pack.
/// Every cell is an `MSStickerView`, so tap-to-send and peel-and-stick work out of the box.
final class PackStickerBrowserViewController: MSStickerBrowserViewController {
    private var stickers: [MSSticker] = []
    private var cache: [String: [MSSticker]] = [:]

    override func viewDidLoad() {
        super.viewDidLoad()
        stickerBrowserView.backgroundColor = .clear
    }

    func show(_ pack: StickerPack) {
        if let cached = cache[pack.id] {
            stickers = cached
        } else {
            stickers = pack.stickers.compactMap { sticker in
                guard let url = sticker.pngURL else { return nil }
                return try? MSSticker(contentsOfFileURL: url,
                                      localizedDescription: String(sticker.accessibilityText.prefix(150)))
            }
            cache[pack.id] = stickers
        }
        stickerBrowserView.reloadData()
        stickerBrowserView.setContentOffset(.zero, animated: false)
    }

    override func numberOfStickers(in stickerBrowserView: MSStickerBrowserView) -> Int {
        stickers.count
    }

    override func stickerBrowserView(_ stickerBrowserView: MSStickerBrowserView, stickerAt index: Int) -> MSSticker {
        stickers[index]
    }
}

private extension UIColor {
    /// Creates a color from a `#RRGGBB` string.
    convenience init(hex: String) {
        let value = UInt64(hex.trimmingCharacters(in: CharacterSet(charactersIn: "#")), radix: 16) ?? 0
        self.init(red: CGFloat((value >> 16) & 0xFF) / 255,
                  green: CGFloat((value >> 8) & 0xFF) / 255,
                  blue: CGFloat(value & 0xFF) / 255,
                  alpha: 1)
    }
}
