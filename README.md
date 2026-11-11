# Crease Segmenter 0.3.3

Blender mesh'lerini yüzey kıvrımlarına veya mevcut bağlantısız parçalara göre böler. Analiz ve segmentasyon yerel olarak çalışır; harici AI modeli kullanmaz.

## Özellikler

- **Smart Analyze:** Mesh'i inceler, segmentasyon açısı ve minimum bölge yüz sayısı önerir.
- **Crease Angle:** Keskin yüzey geçişlerini seçilen açıya göre ayırır.
- **Disconnected Parts:** Yalnızca zaten birbirine bağlı olmayan mesh parçalarını ayırır.
- Sonuçları kaynak objeden ayrı bir `<Model>_Segments` Collection'ında oluşturur.
- Parça pivotlarını kendi merkezlerine taşır; geometriyi sahnedeki yerinde tutar.
- Yeni sonuçları kaynak modelin sağına koyabilir veya kaynak objenin yerine geçebilir.

## Kurulum

1. `CreaseSegmenter-0.3.3.zip` dosyasını indirin.
2. Blender'da **Edit → Preferences → Get Extensions → ⋁ → Install from Disk** seçin.
3. ZIP'i seçip eklentiyi etkinleştirin.
4. 3D View'da `N` tuşuna basıp **Segment** sekmesini açın.

## Kullanım

1. Bir mesh seçip **Analyze Selected Model**'e basın.
2. Öneriyi inceleyin ve segmentasyon modunu seçin.
3. Çıktı olarak **New Model Beside Original** veya **Replace Original** seçin.
4. **Segment Model**'e basın.

Yeni bir mesh seçtiğinizde analiz yenilenmelidir. Mesh seçili değilse eklenti seçim uyarısı gösterir.

## Analiz ve ayarlar

Smart Analyze, komşu yüzlerin normal açılarını ölçüp 85. yüzdelik değerden bir açı önerir. Minimum bölge büyüklüğü, yüz sayısının %0,5'i olarak hesaplanır ve 5–250 yüz aralığında tutulur. Bunlar yerel geometri sezgiselleridir; nesnenin anlamsal türünü tanıyan öğrenilmiş bir AI değildir.

Kesme açısı büyüdükçe daha az bölge oluşur. Minimum bölge yüz sayısı, küçük bölgelerin komşularına katılmasını belirler.

## Sınırlar

UV'ler, renk öznitelikleri ve kullanılan materyaller aktarılır. Shape key'ler, vertex group'lar, armature bağlantıları ve modifier'lar segmentlere aktarılmaz. Sonuç, mesh topolojisine ve seçilen açıya göre değişebilir.
