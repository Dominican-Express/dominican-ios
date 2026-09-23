// Code-drawn brand asset using native CoreGraphics/CoreText, with an opaque RGB canvas.
import Foundation
import CoreGraphics
import CoreText
import ImageIO
import UniformTypeIdentifiers
let side = 1024
let space = CGColorSpaceCreateDeviceRGB()
let context = CGContext(data: nil, width: side, height: side, bitsPerComponent: 8, bytesPerRow: side * 4, space: space, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
let colors = [CGColor(red: 0, green: 0.12, blue: 0.50, alpha: 1), CGColor(red: 0, green: 0.40, blue: 1, alpha: 1)] as CFArray
let gradient = CGGradient(colorsSpace: space, colors: colors, locations: [0, 1])!
context.drawLinearGradient(gradient, start: CGPoint(x: 0, y: 0), end: CGPoint(x: side, y: side), options: [.drawsBeforeStartLocation, .drawsAfterEndLocation])
for i in 0..<8 {
    context.move(to: CGPoint(x: 270 + i * 35, y: -80))
    context.addCurve(to: CGPoint(x: 1150, y: 410 + i * 38), control1: CGPoint(x: 500, y: 760 + i * 30), control2: CGPoint(x: 830, y: 10 + i * 30))
    context.setLineWidth(27)
    context.setStrokeColor(CGColor(red: 0.35, green: 0.72, blue: 1, alpha: 0.22))
    context.strokePath()
}
let font = CTFontCreateWithName("HelveticaNeue-CondensedBlack" as CFString, 140, nil)
for (word, y) in [("DOMINICAN", 530.0), ("EXPRESS", 390.0)] {
    let attrs: [NSAttributedString.Key: Any] = [NSAttributedString.Key(kCTFontAttributeName as String): font, NSAttributedString.Key(kCTForegroundColorAttributeName as String): CGColor(red: 1, green: 1, blue: 1, alpha: 1)]
    let line = CTLineCreateWithAttributedString(NSAttributedString(string: word, attributes: attrs))
    let width = CTLineGetTypographicBounds(line, nil, nil, nil)
    context.textPosition = CGPoint(x: (Double(side) - width) / 2, y: y)
    CTLineDraw(line, context)
}
let output = URL(fileURLWithPath: CommandLine.arguments[1])
let destination = CGImageDestinationCreateWithURL(output as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(destination, context.makeImage()!, nil)
guard CGImageDestinationFinalize(destination) else { fatalError("Could not write icon") }
