import Foundation

/// Display languages. Brand, plan and window names that are English upstream
/// (Session, Weekly, Premium, Credits …) are never catalog keys, so they stay as-is.
public enum AppLanguage: String, CaseIterable, Identifiable {
    case system, zhHans = "zh-Hans", zhHant = "zh-Hant", en, ja, ko, es, fr, de, ptBR = "pt-BR"
    public var id: String { rawValue }
    /// Each language names itself, so it can be found from any current UI language.
    public var nativeName: String {
        switch self {
        case .system: return L10n.tr("跟随系统")
        case .zhHans: return "简体中文"
        case .zhHant: return "繁體中文"
        case .en: return "English"
        case .ja: return "日本語"
        case .ko: return "한국어"
        case .es: return "Español"
        case .fr: return "Français"
        case .de: return "Deutsch"
        case .ptBR: return "Português (Brasil)"
        }
    }
    public static func resolve(_ code: String, preferred: [String] = Locale.preferredLanguages) -> AppLanguage {
        if let explicit = AppLanguage(rawValue: code), explicit != .system { return explicit }
        for tag in preferred {
            let t = tag.lowercased()
            if t.hasPrefix("zh") {
                return t.contains("hant") || t.hasPrefix("zh-tw") || t.hasPrefix("zh-hk") || t.hasPrefix("zh-mo") ? .zhHant : .zhHans
            }
            for language in [AppLanguage.en, .ja, .ko, .es, .fr, .de] where t == language.rawValue || t.hasPrefix(language.rawValue + "-") { return language }
            if t == "pt" || t.hasPrefix("pt-") { return .ptBR }
        }
        return .en
    }
}

/// Simplified Chinese source text is the key. Collector messages reach the UI in
/// that same source form and are translated here, so a language switch applies at once.
public enum L10n {
    public private(set) static var language: AppLanguage = .zhHans
    private static var catalog: [String: [String: String]] = [:]
    private static var patterns: [(key: String, regex: NSRegularExpression)] = []

    public static func load(from url: URL) throws {
        let data = try Data(contentsOf: url)
        guard let doc = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let strings = doc["strings"] as? [String: [String: String]] else {
            throw NSError(domain: "L10n", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid localization catalog"])
        }
        catalog = strings
        patterns = strings.keys.filter { $0.contains("{0}") }.sorted { $0.count > $1.count }.compactMap { key in
            var source = NSRegularExpression.escapedPattern(for: key)
            for index in 0..<4 { source = source.replacingOccurrences(of: "\\{\(index)\\}", with: "(.+?)") }
            return (try? NSRegularExpression(pattern: "^" + source + "$", options: [.dotMatchesLineSeparators])).map { (key, $0) }
        }
    }
    public static var isLoaded: Bool { !catalog.isEmpty }
    public static var keys: Set<String> { Set(catalog.keys) }
    public static func setLanguage(_ code: String) { language = AppLanguage.resolve(code) }

    /// Translate a source key (or collector text) and substitute {0}, {1} … arguments.
    public static func tr(_ text: String, _ args: CustomStringConvertible...) -> String {
        var output = translate(text)
        for (index, value) in args.enumerated() { output = output.replacingOccurrences(of: "{\(index)}", with: value.description) }
        return output
    }

    static func lookup(_ key: String) -> String? {
        guard language != .zhHans, let row = catalog[key] else { return catalog[key] == nil ? nil : key }
        // Traditional Chinese falls back to the source, other languages to English.
        return row[language.rawValue] ?? (language == .zhHant ? key : row["en"])
    }
    static func translate(_ text: String) -> String {
        guard language != .zhHans, !text.isEmpty else { return text }
        if let exact = whole(text) { return exact }
        // Collector text is often assembled from known parts: "general · 当前窗口".
        if text.contains(" · ") {
            let parts = text.components(separatedBy: " · ")
            let translated = parts.map { whole($0) ?? $0 }
            if translated != parts { return translated.joined(separator: " · ") }
        }
        // Several known sentences appended to each other.
        let sentences = text.split(separator: "。", omittingEmptySubsequences: true).map { String($0) + "。" }
        if sentences.count > 1, sentences.joined() == text {
            let translated = sentences.map { whole($0) ?? $0 }
            if translated != sentences { return translated.joined(separator: language == .zhHant || language == .ja ? "" : " ") }
        }
        return text
    }
    /// One complete piece: exact key, a {n} template, or "base（qualifier）".
    private static func whole(_ text: String) -> String? {
        if let exact = lookup(text) { return exact }
        let range = NSRange(text.startIndex..., in: text)
        for (key, regex) in patterns {
            guard let match = regex.firstMatch(in: text, range: range), var output = lookup(key) else { continue }
            for index in 1..<match.numberOfRanges {
                guard let r = Range(match.range(at: index), in: text) else { continue }
                output = output.replacingOccurrences(of: "{\(index - 1)}", with: translate(String(text[r])))
            }
            return output
        }
        if text.hasSuffix("）"), let open = text.lastIndex(of: "（"), open > text.startIndex {
            let base = String(text[..<open]), note = String(text[text.index(after: open)..<text.index(before: text.endIndex)])
            // Only when the base is itself known (or not Chinese); otherwise let segments handle it.
            let head = whole(base) ?? (base.range(of: "\\p{Han}", options: .regularExpression) == nil ? base : nil)
            if let qualifier = lookup(note), let head {
                return language == .zhHant || language == .ja ? head + "（" + qualifier + "）" : head + " (" + qualifier + ")"
            }
        }
        return nil
    }
}
