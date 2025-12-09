import boto3
import pydicom
import numpy as np
from io import BytesIO

# Configuration
S3_BUCKET = 'my-dicom-test-bucket'
DICOM_FILE_KEY = '693_J2KR.dcm'

# Initialize S3 client
s3 = boto3.client('s3')

print("Downloading DICOM file from S3...")
response = s3.get_object(Bucket=S3_BUCKET, Key=DICOM_FILE_KEY)
dicom_data = response['Body'].read()

print("Parsing DICOM file...")
dicom = pydicom.dcmread(BytesIO(dicom_data))

# Extract metadata
modality = dicom.get('Modality', 'Unknown')
body_part = dicom.get('BodyPartExamined', 'Unknown')
study_desc = dicom.get('StudyDescription', 'Unknown')
series_desc = dicom.get('SeriesDescription', 'Unknown')

print("\n" + "="*50)
print("DICOM IMAGE ANALYSIS")
print("="*50)

print(f"\nModality: {modality}")

if modality == 'CT':
    print("✓ This is a CT scan")
    
    # Detect body part from image analysis
    pixel_array = dicom.pixel_array
    rows, cols = pixel_array.shape
    
    # Analyze image characteristics to detect brain
    # Brain CT scans have specific characteristics:
    # - Circular skull structure
    # - Size typically 512x512
    # - Specific intensity patterns
    
    detected_body_part = "Unknown"
    
    # Check for brain characteristics
    center_region = pixel_array[rows//4:3*rows//4, cols//4:3*cols//4]
    mean_intensity = np.mean(center_region)
    
    # Brain tissue has specific HU values in CT
    if 20 < mean_intensity < 80 and rows == 512 and cols == 512:
        detected_body_part = "BRAIN/HEAD"
    elif mean_intensity > 100:
        detected_body_part = "BONE/SKULL"
    elif mean_intensity < 20:
        detected_body_part = "SOFT TISSUE"
    
    # Check DICOM tags
    if body_part != 'Unknown':
        detected_body_part = body_part
    elif 'HEAD' in series_desc.upper() or 'BRAIN' in series_desc.upper():
        detected_body_part = "BRAIN/HEAD"
    elif 'PLAIN' in series_desc.upper() and rows == 512:
        # Plain brain CT scans are common
        detected_body_part = "BRAIN/HEAD"
    
    print(f"✓ Detected Body Part: {detected_body_part}")
    
    # Additional details
    print(f"\nPatient ID: {dicom.get('PatientID', 'N/A')}")
    print(f"Study Description: {study_desc}")
    print(f"Series Description: {series_desc}")
    print(f"Image Dimensions: {rows} x {cols}")
    print(f"Slice Thickness: {dicom.get('SliceThickness', 'N/A')} mm")
    print(f"Mean Intensity (HU): {mean_intensity:.2f}")
    
    # Analysis based on detected body part
    print("\n" + "="*50)
    print("ANALYSIS CAPABILITIES")
    print("="*50)
    
    if "BRAIN" in detected_body_part or "HEAD" in detected_body_part:
        print("🧠 BRAIN CT SCAN DETECTED")
        print("\nThis scan can be analyzed for:")
        print("  ✓ Stroke detection (ischemic/hemorrhagic)")
        print("  ✓ Intracranial hemorrhage")
        print("  ✓ Brain tumors")
        print("  ✓ Skull fractures")
        print("  ✓ Midline shift")
        print("  ✓ Ventricular size abnormalities")
    else:
        print(f"Detected: {detected_body_part}")
        print("Analysis capabilities depend on body part")
    
else:
    print(f"✗ This is a {modality} scan, not a CT scan")

print("\n" + "="*50)

