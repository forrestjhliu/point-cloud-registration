$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
[IO.Directory]::CreateDirectory($root) | Out-Null
[IO.Directory]::CreateDirectory((Join-Path $root 'previews')) | Out-Null

function Color([string]$hex) {
    $hex = $hex.TrimStart('#')
    return [int]([Convert]::ToInt32($hex.Substring(0,2),16) + 256*[Convert]::ToInt32($hex.Substring(2,2),16) + 65536*[Convert]::ToInt32($hex.Substring(4,2),16))
}
$ink='172B3A'; $muted='5C6F7B'; $paper='F6F8FA'; $line='DCE4E9'; $teal='007F78'; $blue='2857B8'; $orange='BD632C'
function Box($s,$x,$y,$w,$h,$fill,$stroke='',$radius=$false) {
    $type=1; if($radius){$type=5}
    $o=$s.Shapes.AddShape($type,[float]$x,[float]$y,[float]$w,[float]$h)
    $o.Fill.ForeColor.RGB=Color $fill
    if($stroke){$o.Line.ForeColor.RGB=Color $stroke; $o.Line.Weight=1}else{$o.Line.Visible=0}
    return $o
}
function Text($s,$x,$y,$w,$h,[string]$value,$size=20,$color='172B3A',$bold=$false,$align=1) {
    $o=$s.Shapes.AddTextbox(1,[float]$x,[float]$y,[float]$w,[float]$h)
    $o.TextFrame.MarginLeft=0; $o.TextFrame.MarginRight=0; $o.TextFrame.MarginTop=0; $o.TextFrame.MarginBottom=0
    $o.TextFrame.WordWrap=-1; $o.TextFrame.AutoSize=0
    $r=$o.TextFrame.TextRange; $r.Text=$value; $r.Font.Name='Microsoft YaHei'; $r.Font.NameFarEast='Microsoft YaHei'
    $r.Font.Size=[float]$size; $r.Font.Color.RGB=Color $color; $r.Font.Bold=[int]$bold*-1
    $r.ParagraphFormat.Alignment=$align; $r.ParagraphFormat.SpaceBefore=0; $r.ParagraphFormat.SpaceAfter=0
    $o.Width=[float]$w; $o.Height=[float]$h
    return $o
}
function Seg($s,$x1,$y1,$x2,$y2,$color='DCE4E9',$weight=1.5,$arrow=$false,$dashed=$false) {
    $o=$s.Shapes.AddLine([float]$x1,[float]$y1,[float]$x2,[float]$y2)
    $o.Line.ForeColor.RGB=Color $color; $o.Line.Weight=[float]$weight
    if($arrow){$o.Line.EndArrowheadStyle=3}; if($dashed){$o.Line.DashStyle=4}
    return $o
}
function Dot($s,$x,$y,$r,$color) {
    $o=$s.Shapes.AddShape(9,[float]($x-$r),[float]($y-$r),[float](2*$r),[float](2*$r))
    $o.Fill.ForeColor.RGB=Color $color; $o.Line.Visible=0
    return $o
}
function Label($s,$x,$y,$w,$value,$accent) {
    [void](Box $s $x $y $w 28 'EAF0F4' '' $true)
    [void](Text $s ($x+10) ($y+4) ($w-20) 22 $value 13 $accent $true)
}
function Header($p,$page,$title,$subtitle,$accent) {
    $s=$p.Slides.Add($p.Slides.Count+1,12)
    $s.FollowMasterBackground=0; $s.Background.Fill.ForeColor.RGB=Color $paper
    [void](Box $s 0 0 960 7 $accent)
    [void](Text $s 40 22 800 20 'SLAI ME2503  ·  课程小项目开题  /  低重叠点云配准' 11 $muted)
    [void](Text $s 40 57 880 48 $title 30 $ink $true)
    [void](Text $s 40 111 880 36 $subtitle 16 $muted)
    [void](Text $s 880 506 40 18 ($page.ToString()+' / 4') 11 $muted $false 3)
    return $s
}
function Footer($s,$text,$url) {
    [void](Seg $s 40 490 920 490 $line 1)
    $o=Text $s 40 504 825 22 $text 9.5 $muted
    if($url){$o.ActionSettings(1).Hyperlink.Address=$url}
}
function Notes($s,[string]$text) { $s.NotesPage.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text=$text }
function Card($s,$x,$y,$w,$h,$title,$body,$accent) {
    [void](Box $s $x $y $w $h 'FFFFFF' $line $true)
    [void](Text $s ($x+18) ($y+15) ($w-36) 28 $title 18 $accent $true)
    [void](Text $s ($x+18) ($y+53) ($w-36) ($h-64) $body 18 $ink)
}
function Metric($s,$x,$y,$w,$big,$title,$desc,$accent) {
    [void](Box $s $x $y $w 99 'FFFFFF' $line $true)
    [void](Text $s ($x+17) ($y+9) ($w-34) 39 $big 28 $accent $true)
    [void](Text $s ($x+17) ($y+48) ($w-34) 23 $title 15 $ink $true)
    [void](Text $s ($x+17) ($y+74) ($w-34) 20 $desc 11.5 $muted)
}
function CloudObject($s,$cx,$cy,$scale=1,$ghost=$true) {
    # Analytic schematic only; these dots are not dataset observations.
    for($row=0;$row -lt 9;$row++){
        for($j=0;$j -lt 13;$j++){
            $a=[math]::PI*($j/12.0)
            $x=$cx+46*$scale*[math]::Cos($a)
            $y=$cy+($row-4)*10*$scale+14*$scale*[math]::Sin($a)
            [void](Dot $s $x $y (1.8*$scale) $teal)
        }
    }
    if($ghost){
        for($j=0;$j -lt 13;$j++){
            $a=[math]::PI+([math]::PI*$j/12.0)
            [void](Dot $s ($cx+46*$scale*[math]::Cos($a)) ($cy+14*$scale*[math]::Sin($a)) (1.5*$scale) 'D9B59C')
        }
    }
}
function Gripper($s,$x,$y,$w,$h,$color,$rotation=0) {
    $ids=@()
    $a=Box $s $x $y $w 9 $color; $ids+=$a.Name
    $a=Box $s $x $y 9 $h $color; $ids+=$a.Name
    $a=Box $s ($x+$w-9) $y 9 $h $color; $ids+=$a.Name
    if($rotation -ne 0){$group=$s.Shapes.Range($ids).Group(); $group.Rotation=$rotation}
}
function RoomCloud($s,$cx,$cy,$angle=0,$variant=0,$scale=1) {
    $a=([double]$angle)*[math]::PI/180
    for($i=0;$i -lt 22;$i++){
        for($j=0;$j -lt 10;$j++){
            if($variant -eq 1 -and $i -gt 14){continue}
            if($variant -eq 2 -and $i -lt 7){continue}
            $x=($i-10.5)*7*$scale; $y=($j-4.5)*5*$scale
            $xx=$x*[math]::Cos($a)-$y*[math]::Sin($a)
            $yy=$x*[math]::Sin($a)+$y*[math]::Cos($a)
            $c=$blue; if($i -ge 7 -and $i -le 14){$c=$teal}
            [void](Dot $s ($cx+$xx) ($cy+$yy) (1.6*$scale) $c)
        }
    }
    for($i=0;$i -lt 13;$i++){
        $x=($i-6)*8*$scale; $y=-58*$scale
        [void](Dot $s ($cx+$x*[math]::Cos($a)-$y*[math]::Sin($a)) ($cy+$x*[math]::Sin($a)+$y*[math]::Cos($a)) (1.9*$scale) '9DAFBC')
    }
}


