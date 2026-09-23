import XCTest

@MainActor
final class DominicanUITests: XCTestCase {
    private let app = XCUIApplication()

    override func setUpWithError() throws {
        continueAfterFailure = false
        app.launchArguments += ["-AppleLanguages", "(es)", "-AppleLocale", "es_ES"]
        app.launch()
        XCTAssertTrue(app.buttons["tab-home"].waitForExistence(timeout: 15))
    }

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func tap(_ label: String) {
        let button = app.buttons[label].firstMatch
        for _ in 0..<4 {
            if button.exists && button.isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(button.exists, label)
        button.tap()
    }

    func testReferenceScreensAndNavigation() {
        capture("01-Inicio")
        tap("tab-cards")
        XCTAssertTrue(app.navigationBars["Mis tarjetas"].exists)
        capture("02-Tarjetas")
        tap("tab-activity")
        XCTAssertTrue(app.navigationBars["Movimientos"].exists)
        capture("03-Movimientos")
        tap("tab-payments")
        XCTAssertTrue(app.navigationBars["Transferir"].exists)
        capture("04-Transferir")
        tap("tab-home")
        tap("Bizum")
        XCTAssertTrue(app.navigationBars["Bizum"].exists)
        capture("05-Bizum")
        app.navigationBars.buttons.firstMatch.tap()
        tap("Cuenta compartida")
        XCTAssertTrue(app.staticTexts["Titulares y permisos"].exists)
        capture("06-Cuenta-compartida")
        app.navigationBars.buttons.firstMatch.tap()
        tap("Insights")
        XCTAssertTrue(app.navigationBars["Insights"].exists)
        capture("07-Insights")
        tap("tab-profile")
        XCTAssertTrue(app.navigationBars["Perfil"].exists)
        capture("08-Perfil")
    }

    func testLargeTextRemainsNavigable() {
        app.terminate()
        app.launchArguments += ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        app.launch()
        XCTAssertTrue(app.buttons["tab-home"].waitForExistence(timeout: 10))
        capture("12-Inicio-texto-accesible")
        tap("tab-cards")
        capture("13-Tarjetas-texto-accesible")
        XCTAssertNoThrow(try app.performAccessibilityAudit(for: [.textClipped]))
        tap("tab-payments")
        tap("Carlos")
        let amount = app.textFields["Importe en euros"]
        app.swipeUp()
        amount.tap()
        amount.typeText("25")
        tap("Listo")
        tap("payment-continue")
        tap("Simular envío")
        XCTAssertTrue(app.staticTexts["Envío simulado"].waitForExistence(timeout: 5))
    }

    func testTransferValidationAndDemoReceipt() {
        tap("tab-payments")
        XCTAssertFalse(app.buttons["payment-continue"].isEnabled)
        tap("Carlos")
        let amount = app.textFields["Importe en euros"]
        amount.tap()
        amount.typeText("25,50")
        tap("Listo")
        tap("payment-continue")
        XCTAssertTrue(app.staticTexts["Revisar envío"].waitForExistence(timeout: 5))
        tap("Simular envío")
        XCTAssertTrue(app.staticTexts["Envío simulado"].waitForExistence(timeout: 5))
        capture("09-Recibo-demo")
        tap("Volver")
        XCTAssertFalse(app.buttons["payment-continue"].isEnabled)
    }

    func testCardBlockAndVerification() {
        tap("tab-cards")
        tap("Bloquear tarjeta")
        XCTAssertTrue(app.buttons["Desbloquear"].exists)
        tap("Desbloquear")
        tap("Ver datos")
        XCTAssertTrue(app.alerts["Verificación demo"].exists)
        tap("Simular verificación")
        XCTAssertTrue(app.navigationBars["Datos de tarjeta"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", "0000 0000 0000 4321")).firstMatch.exists)
        tap("Cerrar")
        XCTAssertTrue(app.buttons["Ver datos"].waitForExistence(timeout: 5))
    }

    func testActivitySearchAndExport() {
        tap("tab-activity")
        let field = app.textFields["Buscar movimientos"]
        field.tap()
        field.typeText("inexistente")
        XCTAssertTrue(app.staticTexts["Sin movimientos"].exists)
        tap("Borrar búsqueda")
        app.swipeDown()
        tap("Transferencias")
        XCTAssertTrue(app.staticTexts["Nómina"].exists)
        XCTAssertFalse(app.staticTexts["Supermercado"].exists)
        tap("Cuenta y extracto")
        tap("Exportar extracto demo")
        XCTAssertTrue(app.otherElements["ActivityListView"].waitForExistence(timeout: 5), app.debugDescription)
        capture("10-Exportar-CSV")
    }

    func testProfileSettingsAndSharedAccount() {
        tap("tab-profile")
        tap("Límites")
        XCTAssertTrue(app.sliders["Límite de gasto mensual"].exists)
        app.sliders["Límite de gasto mensual"].adjust(toNormalizedSliderPosition: 0.6)
        tap("Guardar límites demo")
        XCTAssertTrue(app.alerts["Límites guardados"].exists)
        tap("Aceptar")
        app.navigationBars.buttons.firstMatch.tap()
        tap("Seguridad")
        XCTAssertTrue(app.switches["Saldo bajo"].exists)
        app.switches["Saldo bajo"].tap()
        capture("11-Seguridad")
        tap("tab-home")
        tap("Cuenta compartida")
        tap("Invitar a un nuevo titular")
        tap("Lucía")
        XCTAssertTrue(app.alerts["Invitación simulada"].waitForExistence(timeout: 5))
        tap("Aceptar")
        XCTAssertTrue(app.staticTexts["Invitación demo"].exists)
    }
}
