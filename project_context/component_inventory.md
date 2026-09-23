# Componentes previstos

BrandMark, BankCardView, WavePattern, AvatarView, MoneyText, SectionHeading, TransactionRow, PrimaryButton, MenuRow, SegmentPicker, ContactPicker, FieldLabel, EmptyState, AppTabBar, InsightRing.
Se comparten colores, tipografías, radios, formato monetario y contenedores en DesignSystem y Utilities.

## Implementado
Los componentes previstos existen en `DesignSystem/Components.swift`, `Features/Cards/Components`, `Features/Payments/Components`, `Features/Insights/Components` y `Core/RootView.swift`. Además: DemoFootnote, QuickAction, ContactListView, ScreenStyle y DemoInformationView. El icono se genera con CoreGraphics/CoreText; no añade dependencias a la app.

## View models
BankStore comparte snapshot, preferencias, bloqueos, límites y roles. ActivityViewModel filtra y exporta; PaymentViewModel valida y controla envío/error/recibo; CardsViewModel mantiene selección/hojas; InsightsViewModel calcula períodos y totales. Home/Profile/SharedAccount usan el store observable como view model compartido y estado local para presentación. Las entidades comunes no se duplican en cada módulo.
