// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "AIA-Meetings",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "AIA-Meetings",
            path: "Sources"
        ),
    ]
)
