' MACRO PARA ATUALIZAR A MATÉRIA PRIMA DE PEÇAS FABRICADAS

' Coluna A: Empresa = "001"
' Coluna B: Código (sem "OL", "-" e " ")
' Coluna C: Código da Matéria Prima
' Coluna D: Peso ou metragem (sempre exibido como ="x,yy")
' Coluna E: Perda = "0"

' Regras: Z20 => metragem em m a partir da ÚLTIMA ocorrência "mm"; demais => peso (kg)


Option Explicit

Const DELIM As String = ";"

Dim CODE_PROPS() As String, DESC_PROPS() As String, MAT_PROPS() As String, FALLBACK_CODE_PROPS() As String
Dim gMissingDesc As Object, gMissingMatCode As Object, gZeroValue As Object

Public Sub Main()
    Dim swApp As Object, swModel As Object
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    If swModel Is Nothing Or swModel.GetType <> 2 Then
        MsgBox "Abra uma montagem antes de executar.": Exit Sub
    End If
    
    InitPropNames
    
    Dim dict As Object: Set dict = CreateObject("Scripting.Dictionary")
    dict.CompareMode = vbTextCompare
    
    Set gMissingDesc = CreateObject("Scripting.Dictionary"): gMissingDesc.CompareMode = vbTextCompare
    Set gMissingMatCode = CreateObject("Scripting.Dictionary"): gMissingMatCode.CompareMode = vbTextCompare
    Set gZeroValue = CreateObject("Scripting.Dictionary"): gZeroValue.CompareMode = vbTextCompare
    
    Dim cfg As Object, root As Object
    Set cfg = swModel.GetActiveConfiguration
    Set root = cfg.GetRootComponent3(True)
    If root Is Nothing Then MsgBox "Montagem sem componente raiz válido.": Exit Sub
    
    TraverseComponent root, dict, True
    
    If gMissingDesc.Count > 0 Then ReportMissingDescriptions gMissingDesc
    If gMissingMatCode.Count > 0 Then ReportMissingMaterialCodes gMissingMatCode
    
    ' Verificação: Letra F nos códigos
    CheckForLetterF dict
    
    If dict.Count = 0 Then MsgBox "Nenhum item válido para matéria-prima foi encontrado.": Exit Sub
    
    Dim asmCode As String
    asmCode = GetBOMPartNumber(swModel.GetActiveConfiguration, swModel)
    If Len(Trim$(asmCode)) = 0 Then asmCode = GetFirstProp(swModel, cfg.Name, CODE_PROPS)
    If Len(Trim$(asmCode)) = 0 Then asmCode = GetFirstProp(swModel, cfg.Name, FALLBACK_CODE_PROPS)
    If Len(Trim$(asmCode)) = 0 Then asmCode = BaseName(swModel.GetPathName)
    
    Dim outPath As String
    outPath = BuildDesktopCadastroEquipCsvPath(SanitizeName(asmCode), "ATUALIZAR MATÉRIA PRIMA " & SanitizeName(asmCode) & ".csv")
    
    WriteCsv outPath, dict
    
    If gZeroValue.Count > 0 Then ReportZeroValues gZeroValue
    
    MsgBox "Processo finalizado. CSV gerado em: " & outPath
End Sub

Private Sub TraverseComponent(ByVal comp As Object, ByRef dict As Object, ByVal isRoot As Boolean)
    If comp Is Nothing Or IsSuppressedSafe(comp) Then Exit Sub
    
    If Not isRoot Then
        Dim md As Object: Set md = comp.GetModelDoc2
        If Not md Is Nothing Then
            Dim t As Long: t = md.GetType
            Dim cfgName As String: cfgName = comp.ReferencedConfiguration
            Dim cconf As Object: Set cconf = md.GetConfigurationByName(cfgName)
            
            Dim codeRaw As String
            codeRaw = GetBOMPartNumber(cconf, md)
            If Len(Trim$(codeRaw)) = 0 Then codeRaw = GetFirstProp(md, cfgName, CODE_PROPS)
            If Len(Trim$(codeRaw)) = 0 Then codeRaw = GetFirstProp(md, cfgName, FALLBACK_CODE_PROPS)
            If Len(Trim$(codeRaw)) = 0 Then codeRaw = BaseName(md.GetPathName)
            
            Dim codeClean As String: codeClean = CleanCode(codeRaw)
            Dim descRaw As String: descRaw = GetFirstProp(md, cfgName, DESC_PROPS)
            Dim mpCode As String: mpCode = GetMaterialCode(md, cfgName)
            
            If t = 1 And Len(Trim$(mpCode)) = 0 And InStr(1, codeRaw, "^", vbTextCompare) = 0 Then
                If Left(UCase(codeClean), 1) <> "Z" Then
                    If Not gMissingMatCode.Exists(codeClean) Then gMissingMatCode.Add codeClean, ""
                End If
            End If
            
            If Len(Trim$(mpCode)) > 0 And InStr(1, codeRaw, "^", vbTextCompare) = 0 Then
                If Left(UCase(codeClean), 1) <> "Z" Then
                    If Len(Trim$(descRaw)) = 0 Then
                        If Not gMissingDesc.Exists(codeClean) Then gMissingDesc.Add codeClean, ""
                    Else
                        If Len(Trim$(codeClean)) > 0 And Not dict.Exists(codeClean) Then
                            Dim lenM As Double: lenM = 0#
                            If UCase$(Left$(mpCode, 3)) = "Z20" Then
                                ' calcula em metros já na coleta
                                lenM = GetLengthMetersFromProps(md, cfgName) ' mm -> m [web:19]
                            End If
                            Dim payload As String
                            payload = descRaw & "|" & md.GetPathName & "|" & cfgName & "|" & mpCode & "|" & SerializeNumberInvariant(lenM)
                            dict.Add codeClean, payload
                        End If
                    End If
                End If
            End If
        End If
    End If
    
    Dim kids As Variant: kids = comp.GetChildren
    If IsArray(kids) Then
        Dim i As Long
        For i = LBound(kids) To UBound(kids)
            TraverseComponent kids(i), dict, False
        Next i
    End If
End Sub

' =============== SAÍDA CSV ===============
Private Sub WriteCsv(path As String, dict As Object)
    Dim f As Integer: f = FreeFile
    Open path For Output As #f
    
    ' Escrever cabeçalho
    Print #f, "EMP" & DELIM & "COD" & DELIM & "MAP" & DELIM & "PES" & DELIM & "PER"
    
    ' Criar array com as chaves ordenadas alfabeticamente pela descrição (coluna B)
    Dim keysArray() As String
    Dim keyCount As Long: keyCount = dict.Count
    ReDim keysArray(0 To keyCount - 1)
    
    Dim i As Long: i = 0
    Dim k As Variant
    For Each k In dict.Keys
        keysArray(i) = CStr(k)
        i = i + 1
    Next k
    
    ' Ordenar o array alfabeticamente pelo código do item (coluna B)
    Call QuickSortByCode(keysArray, 0, keyCount - 1)
    
    Dim p() As String, mpCode As String
    Dim outVal As String, dField As String
    
    ' Escrever o CSV com as chaves ordenadas
    For i = 0 To keyCount - 1
        k = keysArray(i)
        p = Split(dict(k), "|") ' 0=desc, 1=path, 2=cfg, 3=mp, 4=lenM(serializado)
        mpCode = p(3)
        
        If UCase$(Left$(mpCode, 3)) = "Z20" Then
            ' RECOMPUTA dos "mm" da descrição para garantir posição correta da vírgula
            Dim lenM As Double
            lenM = ExtractLengthMetersFromText(p(0)) ' usa a última ocorrência “nnn… mm” [web:19]
            If lenM <= 0# Then lenM = ParseNumberInvariant(p(4)) ' fallback seguro [web:26]
            If lenM <= 0# Then
                If Not gZeroValue.Exists(k) Then gZeroValue.Add k, "Metragem zerada"
                GoTo NextItem
            End If
            outVal = Replace(Format(Round(lenM, 2), "0.00"), ".", ",") ' força vírgula e 2 casas [web:26]
        Else
            Dim massKg As Double
            massKg = GetMassKgByFile(p(1), p(2))
            If massKg <= 0# Then
                If Not gZeroValue.Exists(k) Then gZeroValue.Add k, "Peso zerado"
                GoTo NextItem
            End If
            outVal = Replace(Format(Round(massKg, 2), "0.00"), ".", ",") ' "x,yy" [web:26]
        End If
        
        ' trava a vírgula no Excel: ="x,yy"
        dField = "=""" & outVal & """" ' text qualifier via fórmula [web:47]
        
        Print #f, "001" & DELIM & CsvField(CStr(k)) & DELIM & CsvField(mpCode) & DELIM & dField & DELIM & "0"
NextItem:
    Next i
    
    Close #f
End Sub

' =============== ORDENAÇÃO ALFABÉTICA POR CÓDIGO ===============
Private Sub QuickSortByCode(ByRef arr() As String, ByVal low As Long, ByVal high As Long)
    If low < high Then
        Dim pivotIndex As Long: pivotIndex = PartitionByCode(arr, low, high)
        Call QuickSortByCode(arr, low, pivotIndex - 1)
        Call QuickSortByCode(arr, pivotIndex + 1, high)
    End If
End Sub

Private Function PartitionByCode(ByRef arr() As String, ByVal low As Long, ByVal high As Long) As Long
    Dim pivot As String: pivot = arr(high)
    
    Dim i As Long: i = low - 1
    Dim j As Long
    
    For j = low To high - 1
        If StrComp(arr(j), pivot, vbTextCompare) <= 0 Then
            i = i + 1
            Dim temp As String: temp = arr(i): arr(i) = arr(j): arr(j) = temp
        End If
    Next j
    
    Dim temp2 As String: temp2 = arr(i + 1): arr(i + 1) = arr(high): arr(high) = temp2
    PartitionByCode = i + 1
End Function

' =============== EXTRAÇÃO DE MEDIDA ===============
Private Function GetLengthMetersFromProps(ByVal md As Object, ByVal cfgName As String) As Double
    On Error Resume Next
    Dim hit As Double
    
    ' 1) Descrição
    hit = ExtractLengthMetersFromText(GetFirstProp(md, cfgName, DESC_PROPS))
    If hit > 0# Then GetLengthMetersFromProps = hit: Exit Function
    
    ' 2) Campos de MP
    hit = ExtractLengthMetersFromText(GetFirstProp(md, cfgName, MAT_PROPS))
    If hit > 0# Then GetLengthMetersFromProps = hit: Exit Function
    
    ' 3) Todas as propriedades
    Dim ext As Object: Set ext = md.Extension
    Dim mgr As Object, names As Variant, i As Long, v As String, vOut As String, ok As Boolean
    
    Set mgr = ext.CustomPropertyManager(cfgName): names = mgr.GetNames()
    If IsArray(names) Then
        For i = LBound(names) To UBound(names)
            ok = mgr.Get4(names(i), False, v, vOut)
            If ok Then
                hit = ExtractLengthMetersFromText(vOut)
                If hit > 0# Then GetLengthMetersFromProps = hit: Exit Function
            End If
        Next i
    End If
    
    Set mgr = ext.CustomPropertyManager(""): names = mgr.GetNames()
    If IsArray(names) Then
        For i = LBound(names) To UBound(names)
            ok = mgr.Get4(names(i), False, v, vOut)
            If ok Then
                hit = ExtractLengthMetersFromText(vOut)
                If hit > 0# Then GetLengthMetersFromProps = hit: Exit Function
            End If
        Next i
    End If
    
    GetLengthMetersFromProps = 0#
    On Error GoTo 0
End Function

' pega a ÚLTIMA ocorrência "nnn… mm" e converte mm -> m
Private Function ExtractLengthMetersFromText(ByVal s As String) As Double
    On Error Resume Next
    Dim rx As Object: Set rx = CreateObject("VBScript.RegExp")
    rx.Global = True: rx.IgnoreCase = True
    rx.Pattern = "(\d+(?:[.,]\d+)?)\s*mm\b" ' RegExp VBScript [web:19]
    If rx.Test(s) Then
        Dim matches As Object, m As Object, raw As String
        Set matches = rx.Execute(s)
        Set m = matches(matches.Count - 1) ' última ocorrência [web:19]
        raw = m.SubMatches(0)
        raw = Replace(raw, ",", ".")
        If IsNumeric(raw) Then ExtractLengthMetersFromText = CDbl(raw) / 1000# ' mm -> m
    End If
    On Error GoTo 0
End Function

' =============== UTILITÁRIOS/RELATÓRIOS ===============
Private Sub InitPropNames()
    CODE_PROPS = Split("Part Number;Número;Number", ";")
    FALLBACK_CODE_PROPS = Split("Código;Codigo", ";")
    DESC_PROPS = Split("Descrição;Description;Descritivo;Desc", ";")
    MAT_PROPS = Split("Código MP;Codigo MP;Código Materia Prima;Codigo Materia Prima;Código Material;Codigo Material;Material;Matéria prima;Materia prima;MP;Descrição Matéria-prima;Descricao Matéria-prima;Descrição MP;Descricao MP", ";")
End Sub

Private Sub ReportMissingDescriptions(ByVal missing As Object)
    If missing.Count = 0 Then Exit Sub
    Dim msg As String, k As Variant, n As Long
    msg = "Códigos com descrição vazia (" & CStr(missing.Count) & "):" & vbCrLf & vbCrLf
    For Each k In missing.Keys
        n = n + 1
        If n > 100 Then msg = msg & "... (" & CStr(missing.Count - 100) & " mais)" & vbCrLf: Exit For
        msg = msg & CStr(k) & vbCrLf
    Next k
    MsgBox msg, vbInformation, "Faltando Descrição"
End Sub

Private Sub ReportMissingMaterialCodes(ByVal missing As Object)
    If missing.Count = 0 Then Exit Sub
    Dim msg As String, k As Variant, n As Long
    msg = "As seguintes peças fabricadas estão sem Código de Matéria-Prima:" & vbCrLf & vbCrLf
    For Each k In missing.Keys
        n = n + 1
        If n > 100 Then msg = msg & "... (" & CStr(missing.Count - 100) & " mais)" & vbCrLf: Exit For
        msg = msg & CStr(k) & vbCrLf
    Next k
    MsgBox msg, vbExclamation, "Alerta: Matéria-Prima Ausente"
End Sub

Private Sub ReportZeroValues(ByVal zeroItems As Object)
    If zeroItems.Count = 0 Then Exit Sub
    Dim msg As String, k As Variant, n As Long
    msg = "AVISO: Itens ignorados por peso/metragem zerados:" & vbCrLf & vbCrLf
    For Each k In zeroItems.Keys
        n = n + 1
        If n > 100 Then msg = msg & "... (" & CStr(zeroItems.Count - 100) & " mais)" & vbCrLf: Exit For
        msg = msg & CStr(k) & vbCrLf
    Next k
    MsgBox msg, vbInformation, "Itens com Valor Zerado"
End Sub

Private Function GetMaterialCode(ByVal md As Object, ByVal cfgName As String) As String
    Dim s As String, c As String
    s = GetFirstProp(md, cfgName, MAT_PROPS)
    c = ExtractZCodeOr6Digits(s): If Len(c) > 0 Then GetMaterialCode = c: Exit Function
    c = ListAllPropValues_MaterialCode(md, cfgName): GetMaterialCode = c
End Function

Private Function ExtractZCodeOr6Digits(ByVal s As String) As String
    On Error Resume Next
    Dim rx As Object: Set rx = CreateObject("VBScript.RegExp")
    rx.Global = True: rx.IgnoreCase = True
    rx.Pattern = "Z\d{7}": If rx.Test(s) Then ExtractZCodeOr6Digits = rx.Execute(s)(0).value: Exit Function
    rx.Pattern = "Z\d{6}": If rx.Test(s) Then ExtractZCodeOr6Digits = rx.Execute(s)(0).value: Exit Function
    rx.Pattern = "Z\d{5}": If rx.Test(s) Then ExtractZCodeOr6Digits = rx.Execute(s)(0).value: Exit Function
    rx.Pattern = "\d{6}": If rx.Test(s) Then ExtractZCodeOr6Digits = rx.Execute(s)(0).value Else ExtractZCodeOr6Digits = ""
    On Error GoTo 0
End Function

Private Function GetBOMPartNumber(cfg As Object, md As Object) As String
    If cfg Is Nothing Then Exit Function
    Select Case cfg.BOMPartNoSource
        Case 2: GetBOMPartNumber = cfg.AlternateName
        Case 0: GetBOMPartNumber = cfg.Name
        Case 3:
            Dim p As Object: Set p = cfg.GetParent
            If Not p Is Nothing Then GetBOMPartNumber = IIf(Len(p.AlternateName) > 0, p.AlternateName, p.Name)
        Case Else: GetBOMPartNumber = ""
    End Select
End Function

Private Function GetFirstProp(ByVal md As Object, ByVal cfgName As String, ByRef candidates() As String) As String
    On Error Resume Next
    Dim ext As Object: Set ext = md.Extension
    Dim mgr As Object, i As Long, v As String, vOut As String, ok As Boolean
    Set mgr = ext.CustomPropertyManager(cfgName)
    For i = LBound(candidates) To UBound(candidates)
        ok = mgr.Get4(candidates(i), False, v, vOut): If ok And Len(Trim$(vOut)) > 0 Then GetFirstProp = vOut: Exit Function
    Next i
    Set mgr = ext.CustomPropertyManager("")
    For i = LBound(candidates) To UBound(candidates)
        ok = mgr.Get4(candidates(i), False, v, vOut): If ok And Len(Trim$(vOut)) > 0 Then GetFirstProp = vOut: Exit Function
    Next i
    GetFirstProp = ""
    On Error GoTo 0
End Function

Private Function ListAllPropValues_MaterialCode(ByVal md As Object, ByVal cfgName As String) As String
    On Error Resume Next
    Dim ext As Object: Set ext = md.Extension
    Dim mgr As Object, names As Variant, i As Long, v As String, vOut As String, ok As Boolean, hit As String
    Set mgr = ext.CustomPropertyManager(cfgName): names = mgr.GetNames()
    If IsArray(names) Then
        For i = LBound(names) To UBound(names)
            ok = mgr.Get4(names(i), False, v, vOut)
            If ok Then hit = ExtractZCodeOr6Digits(vOut): If Len(hit) > 0 Then ListAllPropValues_MaterialCode = hit: Exit Function
        Next i
    End If
    Set mgr = ext.CustomPropertyManager(""): names = mgr.GetNames()
    If IsArray(names) Then
        For i = LBound(names) To UBound(names)
            ok = mgr.Get4(names(i), False, v, vOut)
            If ok Then hit = ExtractZCodeOr6Digits(vOut): If Len(hit) > 0 Then ListAllPropValues_MaterialCode = hit: Exit Function
        Next i
    End If
    ListAllPropValues_MaterialCode = ""
    On Error GoTo 0
End Function

Private Function GetMassKgByFile(ByVal filePath As String, ByVal cfgName As String) As Double
    Dim v As Variant: v = Application.SldWorks.GetMassProperties2(filePath, cfgName, 1)
    If IsArray(v) And UBound(v) >= 5 Then GetMassKgByFile = CDbl(v(5))
End Function

' serialização invariante para guardar no dicionário
Private Function SerializeNumberInvariant(ByVal x As Double) As String
    SerializeNumberInvariant = Replace(Format(x, "0.################"), ",", ".") ' Format -> string [web:26]
End Function

Private Function ParseNumberInvariant(ByVal s As String) As Double
    Dim t As String: t = Trim$(s)
    If Len(t) = 0 Then ParseNumberInvariant = 0#: Exit Function
    t = Replace(t, ",", ".")
    Dim pDot As Long: pDot = InStrRev(t, ".")
    If pDot > 0 And pDot < Len(t) Then
        Dim intPart As String: intPart = Left$(t, pDot - 1)
        Dim fracPart As String: fracPart = Mid$(t, pDot + 1)
        t = Replace(intPart, ".", "") & "." & fracPart
    Else
        t = Replace(t, ".", "")
    End If
    If IsNumeric(t) Then ParseNumberInvariant = CDbl(t)
End Function

Private Function BuildDesktopCadastroEquipCsvPath(ByVal codigoRaiz As String, ByVal nomeArquivo As String) As String
    Dim folderPath As String
    folderPath = Environ$("USERPROFILE") & "\Desktop\CADASTRO DE EQUIPAMENTOS\CADASTRO " & SanitizeName(codigoRaiz)
    If Len(Dir$(folderPath, vbDirectory)) = 0 Then MkDir folderPath
    BuildDesktopCadastroEquipCsvPath = folderPath & "\" & SanitizeName(nomeArquivo)
End Function

Public Function CleanCode(ByVal s As String) As String
    Dim t As String: t = s
    t = Replace$(t, " ", "", , , vbTextCompare)
    t = Replace$(t, "-", "", , , vbTextCompare)
    t = Replace$(t, "OL", "", , , vbTextCompare)
    CleanCode = t
End Function

Private Function CsvField(ByVal s As String) As String
    If InStr(s, DELIM) Or InStr(s, """") Or InStr(s, vbCr) Or InStr(s, vbLf) Then
        CsvField = """" & Replace(s, """", """""") & """"
    Else
        CsvField = s
    End If
End Function

Private Function BaseName(fullPath As String) As String
    Dim i As Long: i = InStrRev(fullPath, "\")
    BaseName = Mid$(fullPath, i + 1)
    Dim p As Long: p = InStrRev(BaseName, ".")
    If p > 0 Then BaseName = Left$(BaseName, p - 1)
End Function

Private Function IsSuppressedSafe(comp As Object) As Boolean
    On Error Resume Next: IsSuppressedSafe = comp.IsSuppressed: On Error GoTo 0
End Function

Private Function SanitizeName(ByVal s As String) As String
    Dim bad As String: bad = "~""#%&*:<>?{|}/\[];" & Chr(10) & Chr(13)
    Dim i As Long
    For i = 1 To Len(bad): s = Replace$(s, Mid$(bad, i, 1), "_"): Next i
    SanitizeName = Trim$(s)
End Function

' =============== VERIFICAÇÃO DE LETRA F ===============
Private Sub CheckForLetterF(ByRef dict As Object)
    Dim codesWithF As Object: Set codesWithF = CreateObject("Scripting.Dictionary")
    codesWithF.CompareMode = vbTextCompare
    
    Dim k As Variant
    For Each k In dict.Keys
        If InStr(1, CStr(k), "F", vbTextCompare) > 0 Then
            codesWithF.Add CStr(k), dict(k)
        End If
    Next k
    
    If codesWithF.Count > 0 Then
        Dim msg As String: msg = "ATENÇÃO: Foram encontrados " & codesWithF.Count & " códigos contendo a letra 'F':" & vbCrLf & vbCrLf
        For Each k In codesWithF.Keys
            msg = msg & "• " & k & " - " & codesWithF(k) & vbCrLf
        Next k
        MsgBox msg, vbExclamation, "Códigos com Letra F Detectados"
    End If
End Sub
