// lib/screens/pdf_viewer_screen.dart
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:syncfusion_flutter_pdfviewer/pdfviewer.dart';
import 'package:kairos_mobile_app/theme.dart';

class PdfViewerScreen extends StatefulWidget {
  final String filePath;
  final int initialPage;

  const PdfViewerScreen({
    super.key,
    required this.filePath,
    this.initialPage = 1,
  });

  @override
  State<PdfViewerScreen> createState() => _PdfViewerScreenState();
}

class _PdfViewerScreenState extends State<PdfViewerScreen> {
  late final PdfViewerController _pdfViewerController;
  late final File _pdfFile;
  bool _isReady = false;

  @override
  void initState() {
    super.initState();
    _pdfViewerController = PdfViewerController();
    _pdfFile = File(widget.filePath);
    
    // Check if the file exists before trying to display it
    _pdfFile.exists().then((exists) {
      if (exists) {
        setState(() {
          _isReady = true;
        });
        // Jump to the initial page after a short delay to ensure the widget is built
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            _pdfViewerController.jumpToPage(widget.initialPage);
          }
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    // Extract a clean file name from the path to display in the app bar
    final String fileName = widget.filePath.split(Platform.pathSeparator).last;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          fileName,
          style: const TextStyle(fontSize: 16),
        ),
        backgroundColor: AppColors.background,
      ),
      body: _isReady
          ? SfPdfViewer.file(
              _pdfFile,
              controller: _pdfViewerController,
            )
          : const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(color: AppColors.primaryColor),
                  SizedBox(height: 16),
                  Text('Loading Document...'),
                ],
              ),
            ),
    );
  }
}