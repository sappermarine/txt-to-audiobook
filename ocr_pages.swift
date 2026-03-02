import Foundation
import Vision
import AppKit

let screenshotDir = "/Users/sappermarine/kindle_extraction/screenshots"
let outputFile = "/Users/sappermarine/kindle_extraction/book_raw.txt"

// Crop rect to exclude Kindle UI chrome (header ~60px, footer ~60px from bottom)
// Based on the test screenshot: full viewport is ~878px tall, content area is roughly y=60 to y=810
let cropTop: CGFloat = 60
let cropBottom: CGFloat = 60
let cropLeft: CGFloat = 100   // exclude nav arrows
let cropRight: CGFloat = 100  // exclude nav arrows

let fm = FileManager.default
var allFiles = try fm.contentsOfDirectory(atPath: screenshotDir)
    .filter { $0.hasSuffix(".png") }
    .sorted { a, b in
        // Sort by page number: page_001.png, page_002.png, etc.
        let numA = Int(a.replacingOccurrences(of: "page_", with: "").replacingOccurrences(of: ".png", with: "")) ?? 0
        let numB = Int(b.replacingOccurrences(of: "page_", with: "").replacingOccurrences(of: ".png", with: "")) ?? 0
        return numA < numB
    }

print("Found \(allFiles.count) screenshot files to OCR")

var fullText = ""
var processedCount = 0

for file in allFiles {
    let filePath = "\(screenshotDir)/\(file)"
    guard let image = NSImage(contentsOfFile: filePath),
          let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("WARN: Failed to load \(file)")
        continue
    }

    // Crop to content area
    let imgWidth = CGFloat(cgImage.width)
    let imgHeight = CGFloat(cgImage.height)
    let scale: CGFloat = imgWidth / 848.0  // approximate viewport width

    let cropRect = CGRect(
        x: cropLeft * scale,
        y: cropTop * scale,
        width: (imgWidth - (cropLeft + cropRight) * scale),
        height: (imgHeight - (cropTop + cropBottom) * scale)
    )

    let croppedImage: CGImage
    if let cropped = cgImage.cropping(to: cropRect) {
        croppedImage = cropped
    } else {
        croppedImage = cgImage  // fallback to full image
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: croppedImage, options: [:])
    try handler.perform([request])

    guard let results = request.results else { continue }

    var pageLines: [String] = []
    for observation in results {
        if let candidate = observation.topCandidates(1).first {
            pageLines.append(candidate.string)
        }
    }

    let pageText = pageLines.joined(separator: "\n")
    fullText += pageText + "\n\n--- PAGE BREAK ---\n\n"

    processedCount += 1
    if processedCount % 50 == 0 {
        print("Processed \(processedCount)/\(allFiles.count) pages...")
    }
}

// Write output
try fullText.write(toFile: outputFile, atomically: true, encoding: .utf8)
print("Done! Processed \(processedCount) pages. Output written to \(outputFile)")
print("Output size: \(fullText.count) characters")
