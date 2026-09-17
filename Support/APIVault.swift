import Foundation
import Security
import LocalAuthentication

// Separate immutable helper for API-only entries. Does not read Coding Plan
// credentials, browser items, or Claude Code. Secrets are pipe input/output only.
let args=CommandLine.arguments
if args.count == 2 && args[1] == "--identity" { print("__HELPER_ID__|__KEYCHAIN_PREFIX__"); exit(0) }
func quit(_ status: OSStatus, data: Data? = nil, disclose: Bool = false) -> Never {
    if status == errSecSuccess && disclose, let data { FileHandle.standardOutput.write(data) }
    else if let output=try? JSONSerialization.data(withJSONObject:["status":status]) { FileHandle.standardOutput.write(output) }
    exit(status == errSecSuccess ? 0 : status == errSecItemNotFound ? 2 : [errSecInteractionNotAllowed,errSecAuthFailed,errSecUserCanceled].contains(status) ? 3 : 4)
}
guard args.count==3, let uuid=UUID(uuidString:args[2]), ["--read","--save","--delete","--status","--grant"].contains(args[1]) else { quit(errSecParam) }
let service="__KEYCHAIN_PREFIX__api."+uuid.uuidString.lowercased()
var query: [String:Any]=[kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:service,kSecAttrAccount as String:"personal-api"]
if args[1]=="--save" {
    let data=FileHandle.standardInput.readData(ofLength:8193)
    guard !data.isEmpty, data.count<=8192, let text=String(data:data,encoding:.utf8),text.unicodeScalars.allSatisfy({ $0.value>=33 && $0.value<=126 }) else { quit(errSecParam) }
    let attributes=[kSecValueData as String:data]
    let status=SecItemUpdate(query as CFDictionary,attributes as CFDictionary)
    if status==errSecItemNotFound { quit(SecItemAdd(query.merging(attributes){_,new in new} as CFDictionary,nil)) }
    quit(status)
}
if args[1]=="--delete" { let s=SecItemDelete(query as CFDictionary); quit(s==errSecItemNotFound ? errSecSuccess : s) }
query[kSecReturnData as String]=true;query[kSecMatchLimit as String]=kSecMatchLimitOne
if args[1] != "--grant" {
    let context=LAContext();context.interactionNotAllowed=true
    query[kSecUseAuthenticationContext as String]=context
    query[kSecUseAuthenticationUI as String]=kSecUseAuthenticationUIFail
}
var value: CFTypeRef?
let status=SecItemCopyMatching(query as CFDictionary,&value)
quit(status,data:value as? Data,disclose:args[1]=="--read")
