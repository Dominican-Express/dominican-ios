import Foundation
import CoreTransferable
import UniformTypeIdentifiers

struct DemoStatement: Transferable {
    let csv: String
    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(exportedContentType: .commaSeparatedText) { statement in
            Data(statement.csv.utf8)
        }.suggestedFileName("dominican-express-extracto-demo.csv")
    }
}
