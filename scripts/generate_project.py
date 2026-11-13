"""Generate a dependency-free, deterministic Xcode project. Run from repository root."""
from pathlib import Path
import hashlib

def uid(value):
    return hashlib.sha1(value.encode()).hexdigest()[:24].upper()

def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'

root = Path(__file__).resolve().parent.parent
files = sorted(str(p.relative_to(root)) for p in (root / 'Project').rglob('*.swift'))
resources = ['Project/Resources/Assets.xcassets', 'Project/Resources/PrivacyInfo.xcprivacy']
objects = []
def obj(key, body):
    objects.append(f'\t\t{uid(key)} = {{ {body} }};')

for path in files + resources:
    ext = Path(path).suffix
    kind = {'.swift':'sourcecode.swift', '.xcassets':'folder.assetcatalog', '.xcprivacy':'text.xml'}[ext]
    obj('ref:' + path, f'isa = PBXFileReference; lastKnownFileType = {kind}; path = {quote(path)}; sourceTree = SOURCE_ROOT;')
    obj('build:' + path, f'isa = PBXBuildFile; fileRef = {uid("ref:" + path)};')
obj('product', 'isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = DominicanExpress.app; sourceTree = BUILT_PRODUCTS_DIR;')
obj('sources', 'isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = (' + ','.join(uid('build:' + p) for p in files) + '); runOnlyForDeploymentPostprocessing = 0;')
obj('resources', 'isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (' + ','.join(uid('build:' + p) for p in resources) + '); runOnlyForDeploymentPostprocessing = 0;')
obj('frameworks', 'isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;')
obj('sourceGroup', 'isa = PBXGroup; name = Project; children = (' + ','.join(uid('ref:' + p) for p in files + resources) + '); sourceTree = "<group>";')
obj('products', f'isa = PBXGroup; name = Products; children = ({uid("product")},{uid("uiProduct")}); sourceTree = "<group>";')
obj('mainGroup', f'isa = PBXGroup; children = ({uid("sourceGroup")},{uid("uiRef")},{uid("products")}); sourceTree = "<group>";')
common = {
    'CLANG_ENABLE_MODULES':'YES', 'SWIFT_VERSION':'6.0', 'IPHONEOS_DEPLOYMENT_TARGET':'26.0',
    'SDKROOT':'iphoneos', 'TARGETED_DEVICE_FAMILY':'1', 'SUPPORTED_PLATFORMS':'iphoneos iphonesimulator',
    'SUPPORTS_MACCATALYST':'NO', 'SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD':'NO',
    'ASSETCATALOG_COMPILER_APPICON_NAME':'AppIcon', 'GENERATE_INFOPLIST_FILE':'YES', 'INFOPLIST_KEY_CFBundleDisplayName':'Dominican Express',
    'INFOPLIST_KEY_UILaunchScreen_Generation':'YES', 'INFOPLIST_KEY_UIApplicationSceneManifest_Generation':'YES',
    'INFOPLIST_KEY_UISupportedInterfaceOrientations':'UIInterfaceOrientationPortrait',
    'PRODUCT_BUNDLE_IDENTIFIER':'com.dominicanexpress.demo', 'PRODUCT_NAME':'$(TARGET_NAME)',
    'MARKETING_VERSION':'1.0', 'CURRENT_PROJECT_VERSION':'1', 'CODE_SIGN_STYLE':'Automatic',
    'SWIFT_EMIT_LOC_STRINGS':'YES', 'ENABLE_USER_SCRIPT_SANDBOXING':'YES',
    'LD_RUNPATH_SEARCH_PATHS':'$(inherited) @executable_path/Frameworks',
    # Solo la excepción de red local (HTTP al clúster del portátil); se fusiona con el plist generado.
    'INFOPLIST_FILE':'Project/Info.plist'
}
for config in ['Debug', 'Release']:
    settings = common | ({'SWIFT_OPTIMIZATION_LEVEL':'-Onone', 'DEBUG_INFORMATION_FORMAT':'dwarf', 'ENABLE_TESTABILITY':'YES', 'SWIFT_ACTIVE_COMPILATION_CONDITIONS':'DEBUG'} if config == 'Debug' else {'SWIFT_OPTIMIZATION_LEVEL':'-O', 'DEBUG_INFORMATION_FORMAT':'dwarf-with-dsym', 'SWIFT_COMPILATION_MODE':'wholemodule'})
    obj('target' + config, 'isa = XCBuildConfiguration; name = ' + config + '; buildSettings = {' + ''.join(f'{k} = {quote(v)};' for k,v in settings.items()) + '};')
    obj('project' + config, f'isa = XCBuildConfiguration; name = {config}; buildSettings = {{ CLANG_ENABLE_MODULES = YES; }};')
for kind in ['target','project']:
    obj(kind+'Config', f'isa = XCConfigurationList; buildConfigurations = ({uid(kind+"Debug")},{uid(kind+"Release")}); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
obj('target', f'isa = PBXNativeTarget; buildConfigurationList = {uid("targetConfig")}; buildPhases = ({uid("sources")},{uid("frameworks")},{uid("resources")}); buildRules = (); dependencies = (); name = DominicanExpress; productName = DominicanExpress; productReference = {uid("product")}; productType = "com.apple.product-type.application";')
# UI test bundle, kept in the shared scheme for reproducible simulator validation.
ui_file = 'Tests/DominicanUITests/DominicanUITests.swift'
obj('uiRef', f'isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {quote(ui_file)}; sourceTree = SOURCE_ROOT;')
obj('uiBuild', f'isa = PBXBuildFile; fileRef = {uid("uiRef")};')
obj('uiProduct', 'isa = PBXFileReference; explicitFileType = wrapper.cfbundle; includeInIndex = 0; path = DominicanUITests.xctest; sourceTree = BUILT_PRODUCTS_DIR;')
obj('uiSources', f'isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ({uid("uiBuild")}); runOnlyForDeploymentPostprocessing = 0;')
obj('uiFrameworks', 'isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;')
obj('uiProxy', f'isa = PBXContainerItemProxy; containerPortal = {uid("project")}; proxyType = 1; remoteGlobalIDString = {uid("target")}; remoteInfo = DominicanExpress;')
obj('uiDependency', f'isa = PBXTargetDependency; target = {uid("target")}; targetProxy = {uid("uiProxy")};')
for config in ['Debug', 'Release']:
    settings = {'SWIFT_VERSION':'6.0', 'IPHONEOS_DEPLOYMENT_TARGET':'26.0', 'SDKROOT':'iphoneos', 'TARGETED_DEVICE_FAMILY':'1', 'GENERATE_INFOPLIST_FILE':'YES', 'PRODUCT_BUNDLE_IDENTIFIER':'com.dominicanexpress.demo.uitests', 'PRODUCT_NAME':'$(TARGET_NAME)', 'TEST_TARGET_NAME':'DominicanExpress', 'CODE_SIGN_STYLE':'Automatic', 'SWIFT_OPTIMIZATION_LEVEL':'-Onone', 'LD_RUNPATH_SEARCH_PATHS':'$(inherited) @executable_path/Frameworks @loader_path/Frameworks'}
    obj('ui' + config, 'isa = XCBuildConfiguration; name = ' + config + '; buildSettings = {' + ''.join(f'{k} = {quote(v)};' for k,v in settings.items()) + '};')
obj('uiConfig', f'isa = XCConfigurationList; buildConfigurations = ({uid("uiDebug")},{uid("uiRelease")}); defaultConfigurationIsVisible = 0; defaultConfigurationName = Debug;')
obj('uiTarget', f'isa = PBXNativeTarget; buildConfigurationList = {uid("uiConfig")}; buildPhases = ({uid("uiSources")},{uid("uiFrameworks")}); buildRules = (); dependencies = ({uid("uiDependency")}); name = DominicanUITests; productName = DominicanUITests; productReference = {uid("uiProduct")}; productType = "com.apple.product-type.bundle.ui-testing";')
obj('project', f'isa = PBXProject; attributes = {{ LastUpgradeCheck = 2600; }}; buildConfigurationList = {uid("projectConfig")}; compatibilityVersion = "Xcode 16.0"; developmentRegion = es; hasScannedForEncodings = 0; knownRegions = (es, en, Base); mainGroup = {uid("mainGroup")}; productRefGroup = {uid("products")}; projectDirPath = ""; projectRoot = ""; targets = ({uid("target")},{uid("uiTarget")});')
(root/'DominicanExpress.xcodeproj/project.pbxproj').write_text('// !$*UTF8*$!\n{\n\tarchiveVersion = 1;\n\tclasses = {};\n\tobjectVersion = 77;\n\tobjects = {\n' + '\n'.join(objects) + '\n\t};\n\trootObject = ' + uid('project') + ';\n}\n')
scheme = f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="2600" version="1.3">
 <BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{uid('target')}" BuildableName="DominicanExpress.app" BlueprintName="DominicanExpress" ReferencedContainer="container:DominicanExpress.xcodeproj"/></BuildActionEntry></BuildActionEntries></BuildAction>
 <TestAction buildConfiguration="Debug" shouldUseLaunchSchemeArgsEnv="YES"><Testables><TestableReference skipped="NO"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{uid('uiTarget')}" BuildableName="DominicanUITests.xctest" BlueprintName="DominicanUITests" ReferencedContainer="container:DominicanExpress.xcodeproj"/></TestableReference></Testables></TestAction>
 <LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{uid('target')}" BuildableName="DominicanExpress.app" BlueprintName="DominicanExpress" ReferencedContainer="container:DominicanExpress.xcodeproj"/></BuildableProductRunnable><CommandLineArguments><CommandLineArgument argument="-surreal-url http://127.0.0.1:8100" isEnabled="NO"/><CommandLineArgument argument="-surreal-db cluster" isEnabled="NO"/><CommandLineArgument argument="-surreal-user ana@dominican.test" isEnabled="NO"/><CommandLineArgument argument="-surreal-pass demo-ana" isEnabled="NO"/></CommandLineArguments></LaunchAction>
 <ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"><BuildableProductRunnable runnableDebuggingMode="0"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{uid('target')}" BuildableName="DominicanExpress.app" BlueprintName="DominicanExpress" ReferencedContainer="container:DominicanExpress.xcodeproj"/></BuildableProductRunnable></ProfileAction>
 <AnalyzeAction buildConfiguration="Debug"/><ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>'''
(root/'DominicanExpress.xcodeproj/xcshareddata/xcschemes/DominicanExpress.xcscheme').write_text(scheme)
print(f'Generated project with {len(files)} Swift files and {len(resources)} resources.')
