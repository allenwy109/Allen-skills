import Foundation
import PDFKit

struct LinkRecord: Decodable {
    let sourcePage: Int
    let targetPage: Int
    let x: Double
    let y: Double
    let width: Double
    let height: Double
    let pageWidth: Double
    let pageHeight: Double
}

guard CommandLine.arguments.count >= 4 else {
    fputs("usage: link_pdf.swift <links.json> <output.pdf> <page.pdf>...\n", stderr)
    exit(2)
}

let linksURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
let pageURLs = CommandLine.arguments.dropFirst(3).map { URL(fileURLWithPath: $0) }
let links = try JSONDecoder().decode([LinkRecord].self, from: Data(contentsOf: linksURL))
let output = PDFDocument()

for pageURL in pageURLs {
    guard let source = PDFDocument(url: pageURL), let page = source.page(at: 0) else {
        throw NSError(domain: "REPORT_PDF_LINK", code: 1, userInfo: [NSLocalizedDescriptionKey: "cannot read \(pageURL.path)"])
    }
    output.insert(page, at: output.pageCount)
}

for link in links {
    guard let source = output.page(at: link.sourcePage), let target = output.page(at: link.targetPage) else { continue }
    let bounds = source.bounds(for: .mediaBox)
    let scaleX = bounds.width / link.pageWidth
    let scaleY = bounds.height / link.pageHeight
    let rectangle = CGRect(
        x: link.x * scaleX,
        y: bounds.height - ((link.y + link.height) * scaleY),
        width: link.width * scaleX,
        height: link.height * scaleY
    )
    let annotation = PDFAnnotation(bounds: rectangle, forType: .link, withProperties: nil)
    annotation.destination = PDFDestination(page: target, at: CGPoint(x: 0, y: target.bounds(for: .mediaBox).height))
    source.addAnnotation(annotation)
}

guard output.write(to: outputURL) else {
    throw NSError(domain: "REPORT_PDF_LINK", code: 2, userInfo: [NSLocalizedDescriptionKey: "cannot write \(outputURL.path)"])
}
