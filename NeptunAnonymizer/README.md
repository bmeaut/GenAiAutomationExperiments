# Neptun Code Anonymizer

Excel VBA macro for anonymizing Neptun codes using salted SHA-1 hashing to create test data.

## Features

- Anonymizes Neptun codes using SHA-1(salt + code), first 6 characters
- Consistent anonymization: same salt + same code = same result
- Works across multiple worksheets with same salt value
- Two methods: interactive range selection or entire column processing
- Automatically formats cells as text to prevent Excel auto-conversion

## Quick Start

### Installation

1. Open your Excel file with Neptun codes
2. Press `Alt + F11` (VBA Editor)
3. `File > Import File...` → Select `NeptunAnonymizer.bas`
4. Press `Alt + Q` to close VBA Editor

### Usage

**Method 1: Select Range (Recommended)**
1. Press `Alt + F8` (or Developer > Macros)
2. Select `AnonymizeNeptunCodes` → Run
3. Enter salt value (remember this for other worksheets!)
4. Select the range with Neptun codes
5. Done!

**Method 2: Entire Column**
1. Press `Alt + F8`
2. Select `AnonymizeColumn` → Run
3. Enter salt value
4. Enter column letter (e.g., B)
5. Enter starting row (e.g., 2)

## Testing

A test file `TestNeptunCodes.xlsx` is included with sample data:
- Sheet1: 10 students with Neptun codes (includes duplicates)
- Sheet2: 5 course enrollments

**Test with salt "test123" to get these results:**
- ABC123 → E02E6B
- XYZ789 → 130F2A
- DEF456 → 2AF979

Duplicates will have identical anonymized codes!

## Important Notes

⚠️ **BACKUP YOUR DATA FIRST!** Original codes are permanently replaced.

✅ **Use the same salt** across all worksheets for consistency

✅ **Salt is case-sensitive:** "Test123" ≠ "test123"

✅ **Document your salt value** - you'll need it later

## How It Works

```
Input:  Salt = "mysalt", Code = "ABC123"
Step 1: Combine: "mysaltABC123"
Step 2: SHA-1 hash: "e02e6b1a4f... (40 chars)"
Step 3: Take first 6: "E02E6B"
Output: "E02E6B"
```

## Technical Details

- **Algorithm:** SHA-1(salt + NeptunCode)
- **Output:** 6-character hexadecimal (0-9, A-F)
- **Format:** Cells automatically formatted as text (@)
- **Provider:** .NET System.Security.Cryptography.SHA1CryptoServiceProvider

## Troubleshooting

**Macros not appearing?**
- Enable macros: File > Options > Trust Center > Macro Settings > Enable all macros

**Compile error?**
- Requires .NET Framework (standard on Windows)

**Scientific notation (5.27E+12)?**
- This was fixed! Re-import the macro if you see this.

**Wrong results?**
- Verify salt is exactly the same (case-sensitive!)

## Example

Before (with salt "test123"):
```
| Student ID | Neptun Code | Name      |
|------------|-------------|-----------|
| 1          | ABC123      | Student A |
| 2          | XYZ789      | Student B |
| 3          | ABC123      | Student C |
```

After:
```
| Student ID | Neptun Code | Name      |
|------------|-------------|-----------|
| 1          | E02E6B      | Student A |
| 2          | 130F2A      | Student B |
| 3          | E02E6B      | Student C |  ← Same as Student A!
```

## License

Free to use for educational and testing purposes.
