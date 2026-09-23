import Foundation

enum Money {
    static func text(_ amount: Decimal, decimals: Int = 2) -> String {
        let formatter = NumberFormatter()
        // The reference groups four-digit amounts; es_ES defaults to grouping only five digits.
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = "."
        formatter.decimalSeparator = ","
        formatter.groupingSize = 3
        formatter.minimumFractionDigits = decimals
        formatter.maximumFractionDigits = decimals
        formatter.usesGroupingSeparator = true
        return "€ " + (formatter.string(from: amount as NSDecimalNumber) ?? "0,00")
    }

    /// Strict Spanish monetary input: comma decimals, optional dot grouping, max two decimals.
    static func parse(_ input: String) -> Decimal? {
        let clean = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let pattern = #"^(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)(?:,[0-9]{1,2})?$"#
        guard clean.range(of: pattern, options: .regularExpression) != nil else { return nil }
        return Decimal(string: clean.replacingOccurrences(of: ".", with: "").replacingOccurrences(of: ",", with: "."), locale: Locale(identifier: "en_US_POSIX"))
    }

    static func ratio(_ value: Decimal, to total: Decimal) -> Double {
        guard total > 0 else { return 0 }
        return NSDecimalNumber(decimal: value / total).doubleValue
    }
}
