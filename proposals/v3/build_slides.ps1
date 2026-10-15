$ErrorActionPreference='Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'v2\drawing_helpers.ps1')
$root=$PSScriptRoot
$proposalRoot=Split-Path $root -Parent
$assets=Join-Path $proposalRoot 'v2\assets\registration\two_examples'
$deckName='low_overlap_registration_proposal'
$slideCount=12
$script:layoutIssues=[Collections.Generic.List[object]]::new()
$script:slidePlan=[Collections.Generic.List[object]]::new()
$speakerNotes=Get-Content -LiteralPath (Join-Path $root 'speaker_notes.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Add-Type -AssemblyName System.Drawing

function Page($p,$number,[string]$title,[string[]]$points) {
    if($points.Count -lt 1 -or $points.Count -gt 3){throw "Slide $number must contain one to three key points."}
    $script:slidePlan.Add([pscustomobject]@{page=$number;title=$title;key_points=$points})
    $s=$p.Slides.Add($p.Slides.Count+1,12)
    $s.FollowMasterBackground=0
    $s.Background.Fill.ForeColor.RGB=Color $paper
    [void](Box $s 0 0 960 5 $blue)
    [void](Text $s 44 27 750 23 '低重叠点云配准' 12 $muted)
    [void](Text $s 44 70 872 62 $title 31 $ink $true)
    [void](Text $s 826 504 90 23 ($number.ToString()+' / '+$slideCount) 12 $muted $false 3)
    $n=@($speakerNotes | Where-Object {$_.page -eq $number})
    if($n.Count -ne 1){throw "Missing unique speaker notes for slide $number"}
    $noteText=$n[0].notes+"`n`n来源：`n"+($n[0].sources -join "`n")
    if($number -eq 10){$noteText+="`n图中简写 T_P = T_W←P，T_Q = T_W←Q；两者均为 fragment-to-world 参考位姿。"}
    Notes $s $noteText
    return $s
}

function Picture($s,$relative,$x,$y,$w,$h) {
    $path=Join-Path $assets $relative
    $im=[Drawing.Image]::FromFile($path)
    $ratio=[math]::Min($w/$im.Width,$h/$im.Height)
    $pw=$im.Width*$ratio; $ph=$im.Height*$ratio
    $im.Dispose()
    [void]$s.Shapes.AddPicture($path,0,-1,[float]($x+($w-$pw)/2),[float]($y+($h-$ph)/2),[float]$pw,[float]$ph)
}

function CasePanels($s,$group,$sourceId) {
    [void](Text $s 40 175 280 33 '源点云 P' 24 $blue $true 2)
    [void](Text $s 340 175 280 33 '目标点云 Q' 24 $orange $true 2)
    [void](Text $s 640 175 280 33 'GT 对齐（非预测）' 22 $ink $true 2)
    Picture $s ($group+'\input_source.png') 25 212 310 225
    Picture $s ($group+'\input_reference.png') 325 212 310 225
    Picture $s ($group+'\gt_common_surface.png') 625 212 310 225
    [void](Text $s 40 450 280 29 ('片段 '+$sourceId) 20 $muted $false 2)
    [void](Text $s 340 450 280 29 '片段 0' 20 $muted $false 2)
    [void](Text $s 640 450 280 29 '绿：共同表面' 20 $teal $true 2)
}

function ThreeLines($s,[string[]]$lines) {
    for($i=0;$i -lt $lines.Count;$i++){
        $y=191+$i*100
        [void](Text $s 48 $y 55 45 ('0'+($i+1)) 23 $blue $true)
        [void](Text $s 120 ($y-1) 785 55 $lines[$i] 27 $ink $false)
    }
}

function MathText($s,$x,$y,$w,$h,[string]$value,$size=32,$align=2) {
    $clean=''; $indices=[Collections.Generic.List[int]]::new()
    for($j=0;$j -lt $value.Length;$j++){
        if($value[$j] -eq '_' -and $j+1 -lt $value.Length){
            $j++; $indices.Add($clean.Length+1)
        }
        $clean+=$value[$j]
    }
    $o=Text $s $x $y $w $h $clean $size $ink $true $align
    foreach($pos in $indices){
        $f=$o.TextFrame.TextRange.Characters($pos,1).Font
        $f.Size=[float]($size*.72); $f.BaselineOffset=-0.22
    }
    return $o
}

$app=New-Object -ComObject PowerPoint.Application
try {
    $p=$app.Presentations.Add(0)
    $p.PageSetup.SlideWidth=960; $p.PageSetup.SlideHeight=540

    $s=Page $p 1 '机器人换视角后，需要对齐两块局部地图' @('源点云 P','目标点云 Q','GT 展示正确对齐')
    CasePanels $s 'high_3dmatch' '12'

    $s=Page $p 2 '输入：两份尚未对齐的 XYZ 点集' @('两个米制 XYZ 点集','同一静态场景，尺度一致且部分重叠','相对位姿与点对应未知')
    ThreeLines $s @('P ∈ ℝN×3，Q ∈ ℝM×3，单位米','同一静态场景，尺度一致，有部分重叠','相对位姿与点对应未知')
    foreach($shape in $s.Shapes){
        if($shape.HasTextFrame -and $shape.TextFrame.HasText){
            $value=$shape.TextFrame.TextRange.Text
            foreach($dimension in @('N×3','M×3')){
                $start=$value.IndexOf($dimension)
                if($start -ge 0){
                    $font=$shape.TextFrame.TextRange.Characters($start+1,3).Font
                    $font.Size=19; $font.BaselineOffset=0.35
                }
            }
        }
    }

    $s=Page $p 3 '输出：整个 P 共用一个 R,t' @('将源 P 映射到目标 Q','R 是三维旋转','t 是米制平移')
    [void](Text $s 60 188 840 42 '源 P → 目标 Q' 25 $muted $false 2)
    [void](Text $s 60 248 840 86 'p ↦ Rp + t' 54 $blue $true 2)
    [void](Box $s 60 375 400 88 'E8EDF8')
    [void](Text $s 79 401 362 42 'R ∈ SO(3)：三维旋转' 25 $blue $true 2)
    [void](Box $s 500 375 400 88 'E4F1EE')
    [void](Text $s 519 401 362 42 't ∈ ℝ³：平移，单位米' 25 $teal $true 2)

    $s=Page $p 4 '换一个源片段，共同表面明显减少' @('源点云改为片段 30','目标仍是同一片段 0','GT 显示共同表面减少')
    CasePanels $s 'low_3dlomatch' '30'

    $s=Page $p 5 '低重叠，让可靠对应更难找到' @('非重叠区域没有真实对应','重复几何容易造成误匹配')
    Picture $s 'low_3dlomatch\gt_common_surface.png' 35 169 435 315
    [void](Text $s 52 168 392 31 'GT 下的共同表面' 20 $teal $true 2)
    [void](Text $s 524 211 380 88 "非重叠区域`n没有真实对应" 29 $ink $true)
    [void](Text $s 524 365 380 88 "重复的墙面、桌面`n容易造成误匹配" 29 $ink $true)

    $s=Page $p 6 '一个 fragment，是一段扫描的局部表面' @('真实 RGB-D 序列','按参考轨迹融合 50 帧深度','得到局部点云 fragment')
    [void](Box $s 40 210 245 210 'FFFFFF' $line)
    [void](Text $s 58 274 209 92 "RGB-D`n扫描序列" 29 $ink $true 2)
    [void](Seg $s 298 315 335 315 $muted 2 $true)
    [void](Box $s 348 210 267 210 'E8EDF8')
    [void](Text $s 364 260 235 113 "50 帧深度`n按参考轨迹融合" 27 $blue $true 2)
    [void](Seg $s 627 315 664 315 $muted 2 $true)
    Picture $s 'high_3dmatch\input_reference.png' 675 185 255 227
    [void](Text $s 665 427 265 35 '局部点云 fragment' 23 $orange $true 2)

    $s=Page $p 7 '一条样本：两个点云与一个 GT 变换' @('源点云 P 的实际数组','目标点云 Q 的实际数组','GT 变换是监督或评价标签')
    [void](Box $s 40 199 276 247 'FFFFFF' $line)
    [void](Text $s 57 225 242 38 'P：片段 12' 25 $blue $true 2)
    [void](Text $s 57 306 242 55 '16,341 × 3' 32 $ink $true 2)
    [void](Box $s 342 199 276 247 'FFFFFF' $line)
    [void](Text $s 359 225 242 38 'Q：片段 0' 25 $orange $true 2)
    [void](Text $s 359 306 242 55 '18,977 × 3' 32 $ink $true 2)
    [void](Box $s 644 199 276 247 'E4F1EE')
    [void](Text $s 661 225 242 38 '标签 T*' 25 $teal $true 2)
    [void](Text $s 661 298 242 62 '4 × 4' 40 $ink $true 2)
    [void](Text $s 661 394 242 30 '仅用于监督 / 评价' 20 $teal $false 2)

    $s=Page $p 8 '两套测试，主要区别是片段的重叠程度' @('共同的 8 个室内测试场景','3DMatch 常规重叠列表','3DLoMatch 低重叠列表')
    [void](Text $s 50 173 860 49 '同一批 8 个室内测试场景' 28 $ink $true 2)
    [void](Box $s 60 266 400 201 'E8EDF8')
    [void](Text $s 80 283 360 40 '3DMatch' 28 $blue $true 2)
    [void](Text $s 80 336 360 57 '1,623 对' 37 $ink $true 2)
    [void](Text $s 80 413 360 35 '标称 overlap >30%' 23 $blue $false 2)
    [void](Box $s 500 266 400 201 'E4F1EE')
    [void](Text $s 520 283 360 40 '3DLoMatch' 28 $teal $true 2)
    [void](Text $s 520 336 360 57 '1,781 对' 37 $ink $true 2)
    [void](Text $s 520 413 360 35 '标称 overlap 10%–30%' 23 $teal $false 2)

    $s=Page $p 9 '测试配对在各场景间并不均衡' @('八个场景的配对数量分布')
    [void](Box $s 540 156 20 9 $blue)
    [void](Text $s 568 148 140 30 '3DMatch' 18 $muted)
    [void](Box $s 730 156 20 9 $teal)
    [void](Text $s 758 148 158 30 '3DLoMatch' 18 $muted)
    $rows=@(@('RedKitchen',506,525),@('Home AT',156,289),@('Home MD',208,230),@('Hotel UC',226,218),@('Hotel UMD 1',104,158),@('Hotel UMD 3',54,49),@('MIT Studyroom',292,240),@('MIT Lab',77,72))
    for($i=0;$i -lt $rows.Count;$i++){
        $y=197+$i*33
        [void](Text $s 48 $y 181 29 $rows[$i][0] 18 $muted)
        [void](Box $s 245 ($y+3) (620*$rows[$i][1]/550.0) 8.5 $blue)
        [void](Box $s 245 ($y+14) (620*$rows[$i][2]/550.0) 8.5 $teal)
    }
    [void](Seg $s 245 465 865 465 $line 1)
    foreach($tick in @(0,250,500)){
        $x=245+620*$tick/550.0
        [void](Text $s ($x-18) 472 55 24 ([string]$tick) 16 $muted $false 2)
    }
    [void](Text $s 48 472 181 24 '片段对数' 16 $muted)

    $s=Page $p 10 'GT：由已有参考轨迹计算相对变换' @('源片段坐标通过参考位姿进入世界','世界坐标通过目标位姿的逆进入目标','两次变换合成为 GT')
    [void](Box $s 40 213 210 112 'FFFFFF' $line)
    [void](Text $s 58 248 174 44 'P 的局部坐标' 24 $blue $true 2)
    [void](MathText $s 255 194 115 42 'T_P' 24)
    [void](Seg $s 264 270 357 270 $blue 2 $true)
    [void](Box $s 375 213 210 112 'FFFFFF' $line)
    [void](Text $s 393 248 174 44 '世界坐标' 24 $ink $true 2)
    [void](MathText $s 590 194 115 42 'T_Q⁻¹' 24)
    [void](Seg $s 599 270 692 270 $blue 2 $true)
    [void](Box $s 710 213 210 112 'FFFFFF' $line)
    [void](Text $s 728 248 174 44 'Q 的局部坐标' 24 $orange $true 2)
    [void](MathText $s 100 386 760 65 'T* = T_Q⁻¹ T_P' 39)

    $s=Page $p 11 '目标：提高配准成功率' @('官方变换误差小于 0.2 m 判成功','每场景计算有效配对的成功比例','对八场景等权平均得到 RR')
    ThreeLines $s @('官方变换误差 <0.2 m → 此对成功','每个场景：有效配对中的成功比例','对 8 个场景等权平均 → RR')

    $s=Page $p 12 '筛选几何一致的对应，能否更可靠？' @('固定特征与求解器','只改变对应选择规则','比较低重叠 Registration Recall')
    [void](Box $s 40 216 252 216 'FFFFFF' $line)
    [void](Text $s 58 270 216 113 "固定特征`n与 RANSAC" 28 $ink $true 2)
    [void](Seg $s 302 324 337 324 $muted 2 $true)
    [void](Box $s 348 216 264 216 'E8EDF8')
    [void](Text $s 366 258 228 137 "只改变`n对应选择规则" 28 $blue $true 2)
    [void](Seg $s 622 324 657 324 $muted 2 $true)
    [void](Box $s 668 216 252 216 'E4F1EE')
    [void](Text $s 686 266 216 125 "比较低重叠`n配准成功率" 28 $teal $true 2)

    if($p.Slides.Count -ne $slideCount){throw 'Unexpected slide count'}
    foreach($s in $p.Slides){foreach($o in $s.Shapes){
        if($o.HasTextFrame -and $o.TextFrame.HasText){
            $r=$o.TextFrame2.TextRange
            if($r.BoundHeight -gt ($o.Height+4)){
                $script:layoutIssues.Add([pscustomobject]@{slide=$s.SlideIndex;shape=$o.Name;height=$o.Height;bound=$r.BoundHeight;text=$o.TextFrame.TextRange.Text})
            }
        }
    }}
    $p.SaveAs((Join-Path $root ($deckName+'.pptx')),24)
    $p.SaveAs((Join-Path $root ($deckName+'.pdf')),32)
    $preview=Join-Path $root ('previews\'+$deckName)
    [IO.Directory]::CreateDirectory($preview)|Out-Null
    $p.Export($preview,'PNG',1600,900)
    $examples=Join-Path $proposalRoot 'examples'
    [IO.Directory]::CreateDirectory($examples)|Out-Null
    $p.Slides.Item(1).Export((Join-Path $examples '3dmatch_pair_12_to_0.png'),'PNG',3200,1800)
    $p.Slides.Item(4).Export((Join-Path $examples '3dlomatch_pair_30_to_0.png'),'PNG',3200,1800)
    $p.Close()
} finally {
    $app.Quit()
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)
}
ConvertTo-Json -InputObject @($script:slidePlan.ToArray()) -Depth 6 | Set-Content -LiteralPath (Join-Path $root 'slide_plan.json') -Encoding UTF8
ConvertTo-Json -InputObject @($script:layoutIssues.ToArray()) -Depth 6 | Set-Content -LiteralPath (Join-Path $root 'layout_check.json') -Encoding UTF8
Write-Output ('CREATED '+$slideCount+' slides; LAYOUT_OVERFLOWS '+$script:layoutIssues.Count)
& (Join-Path $proposalRoot 'sync_proposal.ps1')
