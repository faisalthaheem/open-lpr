# Open LPR v1.0.1 Release Notes

We're pleased to announce the release of Open LPR v1.0.1! This is a maintenance release that focuses on bug fixes, UI improvements, and enhanced user experience based on feedback from the initial release.

## 🐛 Bug Fixes

### Critical Fixes
- **Fix KeyError in get_first_ocr_text() method**: Handle both new and old OCR data formats to prevent crashes when displaying OCR text on the /images/ page
- **Fix OCR results display in dark mode**: Remove debug styling and ensure proper dark mode compatibility for OCR text and tables
- **Fix pagination URL encoding and error handling**: Resolve issues with pagination functionality on image list pages
- **Fix reverse pagination on image list page**: Correct pagination direction for better user experience
- **Fix hardcoded API response data in LPR processing**: Ensure dynamic and accurate processing results

### UI/UX Fixes
- **Fix display of correct max file size on upload page**: Show accurate file size limits to users
- **Fix duplicate timestamps**: Remove redundant timestamp displays, keeping only processing time
- **Ensure database file ownership**: Prevent readonly database errors in containerized deployments

## ✨ New Features

### User Interface Enhancements
- **Add comprehensive dark mode support**: Implement system theme detection with automatic dark/light mode switching
- **Add favicon for LPR application**: Improve brand recognition with a custom favicon
- **Display annotated images in image list page**: Show processed images with bounding boxes directly in the list view
- **Update index page to show 9 processed images**: Enhance homepage with visual examples of processed images
- **Update UI to show OCR text instead of filename**: Display more meaningful information in image listings
- **Add plate count display**: Show the number of license plates detected in each image

### Layout Improvements
- **Condense vertical space on index page**: Optimize layout for better screen utilization
- **Further condense vertical space and improve layout**: Refine overall UI density and visual hierarchy

## 🔧 Technical Improvements

### Dependencies
- **Update Django from 4.2.7 to 4.2.27**: Include latest security patches and bug fixes
- **Update Pillow from 10.1.0 to 10.3.0**: Incorporate latest image processing improvements and security updates

### Configuration
- **Add CSRF trusted origins configuration**: Enable cross-origin requests for enhanced integration capabilities
- **Add environment file template**: Improve setup experience with configuration examples

### Documentation
- **Improve README organization**: Add collapsible sections and compact navigation for better readability
- **Add comprehensive liability disclaimer to header**: Ensure proper legal coverage
- **Update license to Apache 2.0**: Switch to more permissive open-source license
- **Add live demo section**: Showcase working application for potential users

## 🔄 Changes Since v1.0.0

### File Upload Changes
- **Reduce maximum image upload size from 10MB to 250KB**: Optimize for faster processing and reduced resource usage

### Homepage Updates
- **Updated homepage from generic GitHub to project page**: Provide dedicated project landing page
- **Enhanced visual presentation**: Better showcase of application capabilities

## 📋 API Changes

No breaking changes to the API in this release. All existing endpoints remain compatible with v1.0.0.

## 🐳 Docker Images

The v1.0.1 release includes updated Docker images with the latest fixes and improvements:

- `ghcr.io/faisalthaheem/open-lpr:latest` - Latest stable version (now v1.0.1)
- `ghcr.io/faisalthaheem/open-lpr:v1.0.1` - Version 1.0.1
- `ghcr.io/faisalthaheem/open-lpr:v1.0` - Version 1.0.x series (latest patch)
- `ghcr.io/faisalthaheem/open-lpr:v1` - Version 1.x series (latest minor)

Images are available for both linux/amd64 and linux/arm64 architectures.

## 🔄 Upgrade Instructions

### From v1.0.0 to v1.0.1

#### Docker Deployment
```bash
# Pull the latest image
docker-compose pull

# Restart the services
docker-compose up -d
```

#### LlamaCpp Deployment
```bash
# Pull the latest image
docker-compose -f docker-compose-llamacpp-cpu.yml pull

# Restart the services
docker-compose -f docker-compose-llamacpp-cpu.yml up -d
```

#### Source Installation
```bash
# Pull the latest changes
git fetch origin
git checkout v1.0.1

# Update dependencies
pip install -r requirements.txt

# Restart your application server
```

## 🛠️ Migration Notes

- No database migrations required for this release
- All configuration files remain compatible
- No breaking changes to existing functionality

## 🐛 Known Issues

- Large images (>250KB) are now rejected at upload to ensure optimal performance
- Some very old OCR data formats may require manual migration (contact support if needed)

## 🙏 Acknowledgments

Thank you to all users who reported issues and provided feedback for this release! Your contributions help make Open LPR more reliable and user-friendly.

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

**Thank you for using Open LPR!** 🎉

If you encounter any issues or have questions, please [file an issue](https://github.com/faisalthaheem/open-lpr/issues) on GitHub.

For more information about Open LPR, visit our [main repository](https://github.com/faisalthaheem/open-lpr).